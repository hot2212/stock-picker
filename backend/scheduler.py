"""
定时任务调度 + 自我优化模块
=========================
APScheduler 管理所有定时任务，self_optimizer 每周自动优化参数。
"""

import time
import json
import sqlite3
from datetime import datetime, date, timedelta
from collections import defaultdict

from config import (
    Schedule, DataRetention, OptimizeRange,
    MorningPick, AfternoonPick, update_config
)
import database as db
import picker
import data_fetcher as fetcher


# ════════════════════════════════════════════════════════════
# 定时任务：开盘选股（9:27）
# ════════════════════════════════════════════════════════════
def job_morning_pick():
    """9:27执行开盘选股，保存到数据库"""
    print(f"[{datetime.now()}] === 开盘选股开始 ===")
    try:
        picks = picker.morning_pick()
        today = date.today().strftime("%Y-%m-%d")
        saved_count = 0
        for p in picks:
            p["pick_date"] = today
            db.save_morning_pick(p)
            saved_count += 1
        print(f"[{datetime.now()}] 开盘选股完成，保存 {saved_count} 只")
        return picks
    except Exception as e:
        print(f"[ERROR] 开盘选股失败: {e}")
        return []


# ════════════════════════════════════════════════════════════
# 定时任务：尾盘选股（14:30）
# ════════════════════════════════════════════════════════════
def job_afternoon_pick():
    """14:30执行尾盘选股，保存到数据库"""
    print(f"[{datetime.now()}] === 尾盘选股开始 ===")
    try:
        picks = picker.afternoon_pick()
        today = date.today().strftime("%Y-%m-%d")
        saved_count = 0
        for p in picks:
            p["pick_date"] = today
            db.save_afternoon_pick(p)
            saved_count += 1
        print(f"[{datetime.now()}] 尾盘选股完成，保存 {saved_count} 只")
        return picks
    except Exception as e:
        print(f"[ERROR] 尾盘选股失败: {e}")
        return []


# ════════════════════════════════════════════════════════════
# 定时任务：记录收盘价（15:00）
# ════════════════════════════════════════════════════════════
def job_record_close():
    """15:00记录收盘价，更新追踪数据"""
    print(f"[{datetime.now()}] === 收盘记录开始 ===")
    today = date.today().strftime("%Y-%m-%d")

    try:
        # 获取今日早盘选股
        morning = db.get_morning_picks(today)
        codes = [m["code"] for m in morning]
        if codes:
            quotes = fetcher.tencent_quote(codes)
            for m in morning:
                q = quotes.get(m["code"], {})
                if q:
                    close_price = q.get("price", 0)
                    last_close = q.get("last_close", 0)
                    close_change = 0
                    if last_close > 0:
                        close_change = round((close_price - last_close) / last_close * 100, 2)
                    db.update_morning_track(m["id"], {
                        "close_price": close_price,
                        "close_change": close_change,
                        "is_win": 1 if close_change > 0 else 0,
                    })

        # 获取今日尾盘选股
        afternoon = db.get_afternoon_picks(today)
        codes = [a["code"] for a in afternoon]
        if codes:
            quotes = fetcher.tencent_quote(codes)
            for a in afternoon:
                q = quotes.get(a["code"], {})
                if q:
                    close_price = q.get("price", 0)
                    last_close = q.get("last_close", 0)
                    close_change = 0
                    if last_close > 0:
                        close_change = round((close_price - last_close) / last_close * 100, 2)
                    db.update_afternoon_track(a["id"], {
                        "close_price": close_price,
                        "close_change": close_change,
                    })

        print(f"[{datetime.now()}] 收盘记录完成")
    except Exception as e:
        print(f"[ERROR] 收盘记录失败: {e}")


# ════════════════════════════════════════════════════════════
# 定时任务：清理旧数据
# ════════════════════════════════════════════════════════════
def job_cleanup():
    """每月清理超过30天的选股记录"""
    print(f"[{datetime.now()}] === 数据清理开始 ===")
    try:
        result = db.cleanup_old_records()
        print(f"[{datetime.now()}] 清理完成: 早盘{result['morning']}条, 尾盘{result['afternoon']}条")
    except Exception as e:
        print(f"[ERROR] 数据清理失败: {e}")


# ════════════════════════════════════════════════════════════
# 定时任务：更新板块和题材（盘中）
# ════════════════════════════════════════════════════════════
_cache = {"sectors": None, "themes": None, "sectors_time": 0, "themes_time": 0}

def job_update_sectors():
    """每5分钟更新板块排名（缓存到内存）"""
    try:
        data = fetcher.industry_comparison(10)
        _cache["sectors"] = data
        _cache["sectors_time"] = time.time()
    except Exception as e:
        print(f"[WARN] 更新板块排名失败: {e}")

def job_update_themes():
    """每30分钟更新题材热度（缓存到内存）"""
    try:
        data = fetcher.get_hot_themes()
        _cache["themes"] = data
        _cache["themes_time"] = time.time()
    except Exception as e:
        print(f"[WARN] 更新题材热度失败: {e}")


def get_cached_sectors():
    """获取缓存的板块排名"""
    sectors = _cache.get("sectors")
    if sectors is None:
        return {"top": [], "bottom": [], "total": 0}
    return sectors

def get_cached_themes():
    """获取缓存的题材热度"""
    themes = _cache.get("themes")
    if themes is None:
        return {}
    return themes


# ════════════════════════════════════════════════════════════
# 自我优化模块 —— 每周六/日分析历史数据、自动调参
# ════════════════════════════════════════════════════════════
def job_self_optimize():
    """
    每周自动优化主流程。
    分析近30天历史数据 → 计算各参数最优值 → 更新config → 生成周报
    """
    print(f"[{datetime.now()}] === 自我优化开始 ===")
    try:
        report = optimize_all()
        # 保存周报
        today = date.today()
        week_start = today - timedelta(days=today.weekday() + 7 if today.weekday() < 6 else today.weekday())
        week_end = week_start + timedelta(days=6)
        db.save_weekly_report({
            "report_date": today.strftime("%Y-%m-%d"),
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d"),
            "content": report,
        })
        print(f"[{datetime.now()}] 自我优化完成，周报已保存")
    except Exception as e:
        print(f"[ERROR] 自我优化失败: {e}")


def optimize_all() -> dict:
    """
    全参数优化分析。
    返回优化报告。
    """
    days = DataRetention.PICK_RECORD_DAYS
    morning = db.get_morning_picks(days=days)
    afternoon = db.get_afternoon_picks(days=days)

    report = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_range": f"近{days}天",
        "total_morning": len(morning),
        "total_afternoon": len(afternoon),
        "morning_params": {},
        "afternoon_params": {},
        "recommendations": [],
        "changes_made": [],
    }

    # ── 分析早盘参数 ──
    if morning:
        for amount_threshold in OptimizeRange.COMPETITION_AMOUNT:
            win_count = sum(1 for m in morning if
                           m.get("is_win", 0) == 1)
            # 按竞价金额粗略分组（实际竞价金额未记录，这里用评分相关性代替）
            # 简化处理：统计有评分且盈利的记录
            high_score_wins = sum(1 for m in morning if
                                  (m.get("score", 0) or 0) >= 70 and m.get("is_win", 0) == 1)
            high_score_total = sum(1 for m in morning if (m.get("score", 0) or 0) >= 70)
            if high_score_total > 0:
                report["morning_params"]["high_score_win_rate"] = round(high_score_wins / high_score_total * 100, 1)
                report["morning_params"]["high_score_count"] = high_score_total

        # 计算总胜率
        morning_wins = sum(1 for m in morning if m.get("is_win", 0) == 1)
        report["morning_win_rate"] = round(morning_wins / len(morning) * 100, 1) if morning else 0

        recommendation = ""
        if report.get("morning_win_rate", 0) < 40:
            recommendation = "早盘胜率偏低(<40%)，建议收紧竞价金额门槛或放宽均线条件"
            report["recommendations"].append(recommendation)
            # 自动调整：提高竞价金额门槛
            current = MorningPick.COMPETITION_AMOUNT_MIN
            new_val = min(current * 1.2, 1500_0000)
            update_config("MorningPick", "COMPETITION_AMOUNT_MIN", new_val)
            report["changes_made"].append(f"COMPETITION_AMOUNT_MIN: {current:.0f} → {new_val:.0f}")
        elif report.get("morning_win_rate", 0) > 70:
            recommendation = "早盘胜率偏高(>70%)，可适当放宽条件扩大选股范围"
            report["recommendations"].append(recommendation)

    # ── 分析尾盘参数 ──
    if afternoon:
        afternoon_wins = sum(1 for a in afternoon if a.get("is_win", 0) == 1)
        report["afternoon_win_rate"] = round(afternoon_wins / len(afternoon) * 100, 1) if afternoon else 0

        # 按主力净流入分组统计
        high_inflow_wins = sum(1 for a in afternoon if
                               (a.get("main_net_inflow", 0) or 0) > 1000_0000 and a.get("is_win", 0) == 1)
        high_inflow_total = sum(1 for a in afternoon if (a.get("main_net_inflow", 0) or 0) > 1000_0000)
        if high_inflow_total > 0:
            report["afternoon_params"]["high_inflow_win_rate"] = round(high_inflow_wins / high_inflow_total * 100, 1)

        if report.get("afternoon_win_rate", 0) < 40:
            recommendation = "尾盘胜率偏低(<40%)，建议提高主力净流入门槛或减少选股数量"
            report["recommendations"].append(recommendation)
            current = AfternoonPick.MAIN_NET_INFLOW_MIN
            new_val = min(current * 1.3, 1500_0000)
            update_config("AfternoonPick", "MAIN_NET_INFLOW_MIN", new_val)
            report["changes_made"].append(f"MAIN_NET_INFLOW_MIN: {current:.0f} → {new_val:.0f}")

    # ── 生成总结 ──
    report["summary"] = {
        "morning_win_rate": report.get("morning_win_rate", 0),
        "afternoon_win_rate": report.get("afternoon_win_rate", 0),
        "total_picks": len(morning) + len(afternoon),
        "recommendations": len(report["recommendations"]),
        "changes_made": len(report["changes_made"]),
    }

    return report


# ════════════════════════════════════════════════════════════
# 自选股分析定时更新（盘中每30分钟）
# ════════════════════════════════════════════════════════════
def job_analyze_self_stocks():
    """分析所有自选股，更新分析结果"""
    stocks = db.get_self_stocks()
    for s in stocks:
        try:
            analysis = picker.analyze_self_stock(s["code"])
            db.update_self_stock_analysis(s["id"], analysis)
            time.sleep(0.5)  # 避免并发请求
        except Exception as e:
            print(f"[WARN] 自选股{s['code']}分析失败: {e}")
