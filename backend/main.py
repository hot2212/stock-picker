"""
FastAPI 主入口
============
整合所有模块，提供REST API，启动定时任务。
"""

import json
import logging
from datetime import datetime, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import database as db
import scheduler as sched
import picker
import data_fetcher as fetcher
from config import Schedule

# 日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 定时任务调度器
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def init_scheduler():
    """初始化所有定时任务"""
    # 开盘选股
    scheduler.add_job(
        sched.job_morning_pick,
        CronTrigger(hour=9, minute=27, timezone="Asia/Shanghai"),
        id="morning_pick",
        replace_existing=True,
    )

    # 尾盘选股
    scheduler.add_job(
        sched.job_afternoon_pick,
        CronTrigger(hour=14, minute=30, timezone="Asia/Shanghai"),
        id="afternoon_pick",
        replace_existing=True,
    )

    # 收盘记录
    scheduler.add_job(
        sched.job_record_close,
        CronTrigger(hour=15, minute=0, timezone="Asia/Shanghai"),
        id="record_close",
        replace_existing=True,
    )

    # 板块排名更新（盘中每5分钟）
    scheduler.add_job(
        sched.job_update_sectors,
        IntervalTrigger(minutes=Schedule.SECTOR_INTERVAL_MINUTES),
        id="update_sectors",
        replace_existing=True,
    )

    # 题材热度更新（盘中每30分钟）
    scheduler.add_job(
        sched.job_update_themes,
        IntervalTrigger(minutes=Schedule.THEME_INTERVAL_MINUTES),
        id="update_themes",
        replace_existing=True,
    )

    # 自选股分析更新（盘中每30分钟）
    scheduler.add_job(
        sched.job_analyze_self_stocks,
        IntervalTrigger(minutes=30),
        id="analyze_self",
        replace_existing=True,
    )

    # 自我优化（每周六10:00）
    scheduler.add_job(
        sched.job_self_optimize,
        CronTrigger(day_of_week="sat", hour=10, minute=0, timezone="Asia/Shanghai"),
        id="self_optimize",
        replace_existing=True,
    )

    # 每月1日清理旧数据
    scheduler.add_job(
        sched.job_cleanup,
        CronTrigger(day=1, hour=9, minute=0, timezone="Asia/Shanghai"),
        id="cleanup_data",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("定时任务已启动")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("=== 选股系统启动 ===")
    db.init_db()
    init_scheduler()
    yield
    logger.info("=== 选股系统关闭 ===")
    scheduler.shutdown()


app = FastAPI(
    title="短线选股系统",
    description="基于热门题材+资金流向+技术形态的短线选股系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════
# API 路由
# ════════════════════════════════════════════════════════════

# ---- 今日看板 ----
@app.get("/api/today")
def get_today():
    """获取今日选股数据（包含实时行情）"""
    data = db.get_today_picks()

    # 为所有股票补充实时行情
    all_codes = []
    for key in ["morning", "afternoon_today", "afternoon_yesterday"]:
        for stock in data.get(key, []):
            if stock["code"] not in all_codes:
                all_codes.append(stock["code"])

    quotes = {}
    if all_codes:
        try:
            quotes = fetcher.tencent_quote(all_codes)
        except Exception as e:
            logger.warning(f"获取实时行情失败: {e}")

    # 将实时行情合并到数据中
    for key in ["morning", "afternoon_today", "afternoon_yesterday"]:
        for stock in data.get(key, []):
            q = quotes.get(stock["code"], {})
            stock["realtime"] = {
                "price": q.get("price", 0),
                "change_pct": q.get("change_pct", 0),
                "amount_wan": q.get("amount_wan", 0),
                "turnover_pct": q.get("turnover_pct", 0),
                "vol_ratio": q.get("vol_ratio", 1),
            }

    # 板块排名
    sectors = sched.get_cached_sectors()

    # 题材热度
    themes = sched.get_cached_themes()

    # 大盘指数
    try:
        index_data = fetcher.get_market_index()
    except Exception:
        index_data = {}

    # 尝试获取最新实时数据（如果缓存为空）
    if not sectors.get("top"):
        try:
            sectors = fetcher.industry_comparison(10)
        except Exception:
            pass

    return {
        **data,
        "sectors": sectors,
        "themes": themes,
        "index": index_data,
    }


# ---- 实时行情 ----
@app.get("/api/realtime/{code}")
def get_realtime(code: str):
    """获取单只股票实时行情"""
    try:
        quotes = fetcher.tencent_quote([code])
        if code in quotes:
            return quotes[code]
        return {"error": "股票代码无效"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/realtime/batch")
def get_realtime_batch(codes: list):
    """批量获取实时行情"""
    try:
        quotes = fetcher.tencent_quote(codes)
        return list(quotes.values())
    except Exception as e:
        return {"error": str(e)}


# ---- 自选股管理 ----
@app.get("/api/self-stocks")
def get_self_stocks():
    """获取自选股列表"""
    stocks = db.get_self_stocks()
    # 补充实时行情
    codes = [s["code"] for s in stocks if s["code"]]
    if codes:
        try:
            quotes = fetcher.tencent_quote(codes)
            for s in stocks:
                q = quotes.get(s["code"], {})
                s["realtime"] = {
                    "price": q.get("price", 0),
                    "change_pct": q.get("change_pct", 0),
                }
        except Exception:
            pass
    return stocks


@app.post("/api/self-stocks/add")
def add_self_stock(code: str, name: str = ""):
    """添加自选股并立即分析"""
    # 如果没提供名称，自动获取
    if not name:
        try:
            quotes = fetcher.tencent_quote([code])
            if code in quotes:
                name = quotes[code]["name"]
        except Exception:
            name = code

    # 检查是否已存在
    existing = db.get_self_stock_by_code(code)
    if existing:
        # 重新分析
        analysis = picker.analyze_self_stock(code)
        db.update_self_stock_analysis(existing["id"], analysis)
        return {"id": existing["id"], "message": "已更新分析"}

    # 添加
    stock_id = db.add_self_stock(code, name)
    # 立即分析
    try:
        analysis = picker.analyze_self_stock(code)
        db.update_self_stock_analysis(stock_id, analysis)
    except Exception as e:
        logger.warning(f"自选股{code}首次分析失败: {e}")

    return {"id": stock_id, "message": "添加成功"}


@app.delete("/api/self-stocks/{stock_id}")
def delete_self_stock(stock_id: int):
    """删除自选股"""
    db.delete_self_stock(stock_id)
    return {"message": "删除成功"}


@app.post("/api/self-stocks/{stock_id}/analyze")
def analyze_self_stock(stock_id: int):
    """重新分析自选股"""
    stock = db.get_self_stock(stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="自选股不存在")
    analysis = picker.analyze_self_stock(stock["code"])
    db.update_self_stock_analysis(stock_id, analysis)
    return {**stock, **analysis}


# ---- 历史记录 ----
@app.get("/api/history")
def get_history(days: int = 30):
    """获取历史选股记录"""
    morning = db.get_morning_picks(days=days)
    afternoon = db.get_afternoon_picks(days=days)

    # 按日期分组
    from collections import defaultdict
    by_date = defaultdict(lambda: {"morning": [], "afternoon": []})

    for m in morning:
        d = m["pick_date"]
        by_date[d]["morning"].append(m)

    for a in afternoon:
        d = a["pick_date"]
        by_date[d]["afternoon"].append(a)

    result = []
    for date_str in sorted(by_date.keys(), reverse=True):
        items = by_date[date_str]
        morning_list = items["morning"]
        afternoon_list = items["afternoon"]
        morning_wins = sum(1 for m in morning_list if m.get("is_win"))
        afternoon_wins = sum(1 for a in afternoon_list if a.get("is_win"))

        result.append({
            "date": date_str,
            "morning_count": len(morning_list),
            "morning_wins": morning_wins,
            "morning_rate": round(morning_wins / len(morning_list) * 100, 1) if morning_list else 0,
            "afternoon_count": len(afternoon_list),
            "afternoon_wins": afternoon_wins,
            "afternoon_rate": round(afternoon_wins / len(afternoon_list) * 100, 1) if afternoon_list else 0,
            "morning": morning_list,
            "afternoon": afternoon_list,
        })

    return result


# ---- 准确率看板 ----
@app.get("/api/stats")
def get_stats(days: int = 30):
    """获取统计数据"""
    return db.get_stats(days)


# ---- 板块和题材 ----
@app.get("/api/sectors")
def get_sectors():
    """获取板块排名"""
    return sched.get_cached_sectors()


@app.get("/api/themes")
def get_themes():
    """获取题材热度"""
    return sched.get_cached_themes()


@app.get("/api/index")
def get_index():
    """获取大盘指数"""
    try:
        return fetcher.get_market_index()
    except Exception as e:
        return {"error": str(e)}


# ---- 周报 ----
@app.get("/api/weekly-reports")
def get_weekly_reports(limit: int = 10):
    """获取周报列表"""
    return db.get_weekly_reports(limit)


# ---- 手动触发选股（调试用） ----
@app.post("/api/trigger/morning-pick")
def trigger_morning_pick():
    """手动触发开盘选股"""
    picks = sched.job_morning_pick()
    return {"count": len(picks), "picks": picks}


@app.post("/api/trigger/afternoon-pick")
def trigger_afternoon_pick():
    """手动触发尾盘选股"""
    picks = sched.job_afternoon_pick()
    return {"count": len(picks), "picks": picks}


@app.post("/api/trigger/optimize")
def trigger_optimize():
    """手动触发自我优化"""
    sched.job_self_optimize()
    return {"message": "优化完成"}


# ---- 系统状态 ----
@app.get("/api/status")
def get_status():
    """系统状态"""
    jobs = scheduler.get_jobs()
    return {
        "status": "running",
        "scheduler_jobs": [
            {"id": j.id, "next_run": str(j.next_run_time)} for j in jobs
        ],
        "sectors_cached": sched.get_cached_sectors().get("total", 0),
        "themes_cached": len(sched.get_cached_themes()),
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ════════════════════════════════════════════════════════════
# 启动入口
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
