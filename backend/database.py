"""
数据库模块
=========
SQLite 数据模型和 CRUD 操作。
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from config import DB_PATH, DataRetention


# ============================================================
# 数据库初始化
# ============================================================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    cur = conn.cursor()

    # ---- 早盘选股记录 ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS morning_picks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_date   TEXT NOT NULL,           -- 选股日期 YYYY-MM-DD
            code        TEXT NOT NULL,           -- 股票代码
            name        TEXT NOT NULL,           -- 股票名称
            pick_price  REAL,                    -- 选股时价格
            pick_change REAL,                    -- 选股时涨幅
            competition_amount REAL,             -- 竞价金额
            competition_change REAL,             -- 竞价涨幅
            competition_vol_ratio REAL,          -- 竞价量比
            sector      TEXT,                    -- 所属板块
            sector_rank INTEGER,                 -- 板块排名
            reason      TEXT,                    -- 选股理由
            score       REAL,                    -- 综合评分
            -- 追踪数据（自动更新）
            close_price   REAL,                  -- 当日收盘价
            close_change  REAL,                  -- 当日收盘涨幅
            next_open     REAL,                  -- 次日开盘价
            next_close    REAL,                  -- 次日收盘价
            next_change   REAL,                  -- 次日涨幅
            hold_1day_max REAL,                  -- 持有1日最高涨幅
            hold_2day_max REAL,                  -- 持有2日最高涨幅
            is_win        INTEGER DEFAULT 0,     -- 是否盈利
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---- 尾盘选股记录 ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS afternoon_picks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_date   TEXT NOT NULL,
            code        TEXT NOT NULL,
            name        TEXT NOT NULL,
            pick_price  REAL,
            pick_change REAL,
            turnover    REAL,                    -- 当日成交额
            main_net_inflow REAL,                -- 主力净流入
            tail_change REAL,                    -- 尾盘阶段涨幅
            sector      TEXT,
            reason      TEXT,
            score       REAL,
            -- 追踪数据
            close_price   REAL,
            close_change  REAL,
            next_open     REAL,
            next_close    REAL,
            next_change   REAL,
            hold_1day_max REAL,
            hold_2day_max REAL,
            is_win        INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---- 自选股分析记录 ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS self_stocks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL,            -- 股票代码
            name        TEXT NOT NULL,            -- 股票名称
            added_date  TEXT NOT NULL,            -- 添加日期
            -- 最新分析
            analysis_date   TEXT,                 -- 最近分析日期
            price           REAL,                 -- 分析时价格
            score           REAL,                 -- 综合评分
            score_detail    TEXT,                 -- 评分明细(JSON)
            buy_advice      TEXT,                 -- 买入建议
            buy_range_low   REAL,                 -- 买入区间下限
            buy_range_high  REAL,                 -- 买入区间上限
            target_price1   REAL,                 -- 第一目标价
            target_price2   REAL,                 -- 第二目标价
            stop_loss       REAL,                 -- 止损价
            analysis_reason TEXT,                 -- 分析依据
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---- 周报记录 ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,            -- 周报日期（周日）
            week_start  TEXT NOT NULL,            -- 本周起始
            week_end    TEXT NOT NULL,            -- 本周结束
            content     TEXT NOT NULL,            -- 周报内容(JSON)
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# 早盘选股 CRUD
# ============================================================
def save_morning_pick(pick_data: dict) -> int:
    """保存一条早盘选股记录，返回ID"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO morning_picks (
            pick_date, code, name, pick_price, pick_change,
            competition_amount, competition_change, competition_vol_ratio,
            sector, sector_rank, reason, score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pick_data["pick_date"], pick_data["code"], pick_data["name"],
        pick_data.get("pick_price"), pick_data.get("pick_change"),
        pick_data.get("competition_amount"), pick_data.get("competition_change"),
        pick_data.get("competition_vol_ratio"), pick_data.get("sector"),
        pick_data.get("sector_rank"), pick_data.get("reason"),
        pick_data.get("score")
    ))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_morning_track(pick_id: int, track_data: dict):
    """更新早盘选股的追踪数据（收盘/次日）"""
    conn = get_connection()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ["close_price", "close_change", "next_open", "next_close",
                "next_change", "hold_1day_max", "hold_2day_max", "is_win"]:
        if key in track_data:
            fields.append(f"{key}=?")
            values.append(track_data[key])
    if fields:
        values.append(pick_id)
        cur.execute(
            f"UPDATE morning_picks SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            values
        )
        conn.commit()
    conn.close()


def get_morning_picks(date: str = None, days: int = 30):
    """获取早盘选股记录"""
    conn = get_connection()
    cur = conn.cursor()
    if date:
        cur.execute("SELECT * FROM morning_picks WHERE pick_date=? ORDER BY id", (date,))
    else:
        cur.execute(
            "SELECT * FROM morning_picks WHERE pick_date>=date('now', ?) ORDER BY pick_date DESC, id",
            (f"-{days} days",)
        )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ============================================================
# 尾盘选股 CRUD
# ============================================================
def save_afternoon_pick(pick_data: dict) -> int:
    """保存一条尾盘选股记录"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO afternoon_picks (
            pick_date, code, name, pick_price, pick_change,
            turnover, main_net_inflow, tail_change,
            sector, reason, score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pick_data["pick_date"], pick_data["code"], pick_data["name"],
        pick_data.get("pick_price"), pick_data.get("pick_change"),
        pick_data.get("turnover"), pick_data.get("main_net_inflow"),
        pick_data.get("tail_change"), pick_data.get("sector"),
        pick_data.get("reason"), pick_data.get("score")
    ))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_afternoon_track(pick_id: int, track_data: dict):
    """更新尾盘选股的追踪数据"""
    conn = get_connection()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ["close_price", "close_change", "next_open", "next_close",
                "next_change", "hold_1day_max", "hold_2day_max", "is_win"]:
        if key in track_data:
            fields.append(f"{key}=?")
            values.append(track_data[key])
    if fields:
        values.append(pick_id)
        cur.execute(
            f"UPDATE afternoon_picks SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            values
        )
        conn.commit()
    conn.close()


def get_afternoon_picks(date: str = None, days: int = 30):
    """获取尾盘选股记录"""
    conn = get_connection()
    cur = conn.cursor()
    if date:
        cur.execute("SELECT * FROM afternoon_picks WHERE pick_date=? ORDER BY id", (date,))
    else:
        cur.execute(
            "SELECT * FROM afternoon_picks WHERE pick_date>=date('now', ?) ORDER BY pick_date DESC, id",
            (f"-{days} days",)
        )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ============================================================
# 自选股 CRUD
# ============================================================
def add_self_stock(code: str, name: str) -> int:
    """添加自选股"""
    conn = get_connection()
    cur = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO self_stocks (code, name, added_date) VALUES (?, ?, ?)",
        (code, name, today)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def delete_self_stock(stock_id: int):
    """删除自选股"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM self_stocks WHERE id=?", (stock_id,))
    conn.commit()
    conn.close()


def get_self_stocks():
    """获取所有自选股"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM self_stocks ORDER BY added_date DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_self_stock(stock_id: int):
    """获取单个自选股"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM self_stocks WHERE id=?", (stock_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_self_stock_by_code(code: str):
    """通过代码获取自选股"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM self_stocks WHERE code=?", (code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_self_stock_analysis(stock_id: int, analysis: dict):
    """更新自选股分析结果"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE self_stocks SET
            analysis_date=?, price=?, score=?, score_detail=?,
            buy_advice=?, buy_range_low=?, buy_range_high=?,
            target_price1=?, target_price2=?, stop_loss=?,
            analysis_reason=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        analysis.get("analysis_date"),
        analysis.get("price"),
        analysis.get("score"),
        json.dumps(analysis.get("score_detail", {}), ensure_ascii=False),
        analysis.get("buy_advice"),
        analysis.get("buy_range_low"),
        analysis.get("buy_range_high"),
        analysis.get("target_price1"),
        analysis.get("target_price2"),
        analysis.get("stop_loss"),
        analysis.get("analysis_reason"),
        stock_id
    ))
    conn.commit()
    conn.close()


# ============================================================
# 周报 CRUD
# ============================================================
def save_weekly_report(report_data: dict) -> int:
    """保存周报"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO weekly_reports (report_date, week_start, week_end, content)
        VALUES (?, ?, ?, ?)
    """, (
        report_data["report_date"],
        report_data["week_start"],
        report_data["week_end"],
        json.dumps(report_data["content"], ensure_ascii=False)
    ))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_weekly_reports(limit: int = 10):
    """获取周报列表"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM weekly_reports ORDER BY report_date DESC LIMIT ?",
        (limit,)
    )
    rows = [dict(row) for row in cur.fetchall()]
    for r in rows:
        r["content"] = json.loads(r["content"])
    conn.close()
    return rows


# ============================================================
# 数据清理
# ============================================================
def cleanup_old_records():
    """清理超过30天的选股记录"""
    cutoff = (datetime.now() - timedelta(days=DataRetention.PICK_RECORD_DAYS)).strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM morning_picks WHERE pick_date<?", (cutoff,))
    m_count = cur.rowcount
    cur.execute("DELETE FROM afternoon_picks WHERE pick_date<?", (cutoff,))
    a_count = cur.rowcount
    conn.commit()
    conn.close()
    return {"morning": m_count, "afternoon": a_count}


# ============================================================
# 统计数据（用于准确率看板）
# ============================================================
def get_stats(days: int = 30):
    """获取统计数据"""
    conn = get_connection()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 早盘统计
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN hold_1day_max IS NOT NULL THEN hold_1day_max ELSE 0 END) as avg_hold_1day,
            AVG(CASE WHEN hold_2day_max IS NOT NULL THEN hold_2day_max ELSE 0 END) as avg_hold_2day
        FROM morning_picks WHERE pick_date>=?
    """, (cutoff,))
    morning_stat = dict(cur.fetchone())

    # 尾盘统计
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN hold_1day_max IS NOT NULL THEN hold_1day_max ELSE 0 END) as avg_hold_1day,
            AVG(CASE WHEN hold_2day_max IS NOT NULL THEN hold_2day_max ELSE 0 END) as avg_hold_2day
        FROM afternoon_picks WHERE pick_date>=?
    """, (cutoff,))
    afternoon_stat = dict(cur.fetchone())

    # 每日胜率趋势
    cur.execute("""
        SELECT pick_date,
               COUNT(*) as total,
               SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins
        FROM (
            SELECT pick_date, is_win FROM morning_picks WHERE pick_date>=?
            UNION ALL
            SELECT pick_date, is_win FROM afternoon_picks WHERE pick_date>=?
        ) GROUP BY pick_date ORDER BY pick_date
    """, (cutoff, cutoff))
    daily_trend = [dict(row) for row in cur.fetchall()]

    conn.close()

    def safe_rate(stat):
        total = stat["total"] or 0
        wins = stat["wins"] or 0
        return round(wins / total * 100, 1) if total > 0 else 0

    return {
        "morning": {
            "total": morning_stat["total"] or 0,
            "wins": morning_stat["wins"] or 0,
            "win_rate": safe_rate(morning_stat),
            "avg_hold_1day": round((morning_stat["avg_hold_1day"] or 0) * 100, 2),
            "avg_hold_2day": round((morning_stat["avg_hold_2day"] or 0) * 100, 2),
        },
        "afternoon": {
            "total": afternoon_stat["total"] or 0,
            "wins": afternoon_stat["wins"] or 0,
            "win_rate": safe_rate(afternoon_stat),
            "avg_hold_1day": round((afternoon_stat["avg_hold_1day"] or 0) * 100, 2),
            "avg_hold_2day": round((afternoon_stat["avg_hold_2day"] or 0) * 100, 2),
        },
        "daily_trend": [
            {"date": d["pick_date"], "total": d["total"], "wins": d["wins"],
             "rate": round(d["wins"] / d["total"] * 100, 1) if d["total"] > 0 else 0}
            for d in daily_trend
        ]
    }


# ============================================================
# 获取今日选股（前端轮询用）
# ============================================================
def get_today_picks():
    """获取今天的选股 + 昨天尾盘（带实时行情占位）"""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM morning_picks WHERE pick_date=? ORDER BY id", (today,))
    morning = [dict(row) for row in cur.fetchall()]

    cur.execute("SELECT * FROM afternoon_picks WHERE pick_date=? ORDER BY id", (today,))
    afternoon_today = [dict(row) for row in cur.fetchall()]

    cur.execute("SELECT * FROM afternoon_picks WHERE pick_date=? ORDER BY id", (yesterday,))
    afternoon_yesterday = [dict(row) for row in cur.fetchall()]

    conn.close()
    now_hour = datetime.now().hour
    now_min = datetime.now().minute
    afternoon_time_passed = (now_hour > 14) or (now_hour == 14 and now_min >= 30)

    return {
        "date": today,
        "morning": morning,
        "afternoon_today": afternoon_today,
        "afternoon_yesterday": afternoon_yesterday,
        "morning_ready": len(morning) > 0,
        "morning_ran": True,  # 已过9:27说明已执行
        "afternoon_ready": len(afternoon_today) > 0,
        "afternoon_ran": afternoon_time_passed,  # 是否已过14:30
        "afternoon_has_result": len(afternoon_today) > 0,
    }
