"""
选股引擎模块
===========
开盘选股(9:27)、尾盘选股(14:30)、自选股分析的核心逻辑。
"""

import time
from datetime import datetime, date
from typing import Optional

from config import MorningPick, AfternoonPick, ScoreWeights
import data_fetcher as fetcher


# ════════════════════════════════════════════════════════════
# 一、开盘选股（9:27）
# ════════════════════════════════════════════════════════════
def morning_pick() -> list:
    """
    开盘选股主流程。
    1. 获取热门板块TOP5
    2. 获取同花顺热点强势股
    3. 过滤：竞价条件 + 盘面条件 + 均线确认
    4. 排序取前5
    """
    today = date.today().strftime("%Y-%m-%d")
    results = []

    # ── 第1步：获取板块排名 ──
    try:
        sector_data = fetcher.industry_comparison(MorningPick.SECTOR_RANK_TOP_N)
        top_sectors = [s["name"] for s in sector_data.get("top", [])]
    except Exception as e:
        print(f"[WARN] 获取板块排名失败: {e}")
        top_sectors = []

    # ── 第2步：获取同花顺热点强势股 ──
    try:
        hot_stocks = fetcher.ths_hot_reason(today)
    except Exception as e:
        print(f"[WARN] 获取同花顺热点失败: {e}")
        hot_stocks = []

    if not hot_stocks:
        print("[WARN] 同花顺热点无数据，尝试从强势股中筛选...")
        return []

    # ── 第3步：获取这些股票的实时行情 ──
    codes = [s["code"] for s in hot_stocks]
    quotes = {}
    try:
        quotes = fetcher.tencent_quote(codes)
    except Exception as e:
        print(f"[WARN] 获取腾讯行情失败: {e}")

    # ── 第4步：逐只筛选 ──
    candidates = []
    for stock in hot_stocks:
        code = stock["code"]
        q = quotes.get(code, {})

        # 基础信息
        name = stock.get("name", "")
        price = q.get("price", stock.get("close", 0))
        change_pct = q.get("change_pct", stock.get("zhangfu", 0))
        amount_wan = q.get("amount_wan", 0)
        turnover_pct = q.get("turnover_pct", stock.get("huanshou", 0))
        vol_ratio = q.get("vol_ratio", 0)
        mcap = q.get("float_mcap_yi", 0) * 1e8  # 转元
        reason_tags = stock.get("reason", "")

        # 判断是否属于热门板块
        in_hot_sector = any(s in reason_tags for s in top_sectors) if top_sectors else True

        # ── 硬性过滤 ──
        # 涨幅范围
        if change_pct < MorningPick.PRICE_CHANGE_MIN or change_pct > MorningPick.PRICE_CHANGE_MAX:
            continue

        # 成交额
        if amount_wan < MorningPick.TURNOVER_MIN / 10000:
            continue

        # 换手率
        if turnover_pct < MorningPick.TURNOVER_RATE_MIN * 100 or turnover_pct > MorningPick.TURNOVER_RATE_MAX * 100:
            continue

        # 量比
        if vol_ratio < MorningPick.VOL_RATIO_MIN:
            continue

        # 流通市值
        # if mcap < MorningPick.MARKET_VALUE_MIN or mcap > MorningPick.MARKET_VALUE_MAX:
        #     continue

        # 板块过滤（放宽：如果不在TOP5板块但题材够热也保留）
        sector_score = 2 if in_hot_sector else 0

        # ── 均线确认 ──
        try:
            ma_status = fetcher.get_ma_status(code)
            trend_up = ma_status.get("trend_up", False)
            vol_ratio_ma5 = ma_status.get("vol_ratio_ma5", 0)
        except Exception:
            ma_status = {}
            trend_up = False
            vol_ratio_ma5 = 0

        # 如果均线多头加分
        tech_score = 3 if trend_up else 0
        vol_score = 1 if vol_ratio_ma5 > 1.2 else 0

        # ── 题材热度评分 ──
        theme_keywords = reason_tags.split("+") if reason_tags else []
        theme_score = min(len(theme_keywords) * 10, 25)  # 每个题材标签10分，上限25

        # ── 综合评分 ──
        total_score = sector_score + tech_score + vol_score + round(theme_score / 10, 1)

        # 选股理由
        reasons = []
        if in_hot_sector:
            reasons.append("热门板块")
        if trend_up:
            reasons.append("均线多头")
        if vol_ratio > 1.5:
            reasons.append("放量")
        if reason_tags:
            reasons.append(f"题材:{reason_tags[:30]}")

        candidates.append({
            "code": code,
            "name": name,
            "pick_price": round(price, 2),
            "pick_change": round(change_pct, 2),
            "amount_wan": amount_wan,
            "turnover_pct": turnover_pct,
            "vol_ratio": vol_ratio,
            "sector": top_sectors[0] if top_sectors else "",
            "sector_rank": 1,
            "reason": " + ".join(reasons),
            "score": total_score,
            "ma_status": trend_up,
            "in_hot_sector": in_hot_sector,
            "theme_tags": reason_tags,
        })

    # ── 第5步：排序取前N ──
    # 排序规则：均线多头优先 > 热门板块优先 > 评分
    candidates.sort(key=lambda x: (
        x["ma_status"],
        x["in_hot_sector"],
        x["score"]
    ), reverse=True)

    results = candidates[:MorningPick.PICK_COUNT]

    # 补充分数详细
    for r in results:
        r["score"] = round(min(r["score"] * 10, 100), 1)

    return results


# ════════════════════════════════════════════════════════════
# 二、尾盘选股（14:30）
# ════════════════════════════════════════════════════════════
def afternoon_pick() -> list:
    """
    尾盘选股主流程。
    埋伏次日会涨的票，关注尾盘资金动向。
    """
    today = date.today().strftime("%Y-%m-%d")
    results = []

    # ── 第1步：获取热门板块和热点股 ──
    sector_data = None
    try:
        sector_data = fetcher.industry_comparison(AfternoonPick.SECTOR_RANK_TOP_N)
        top_sectors = [s["name"] for s in sector_data.get("top", [])]
    except Exception:
        top_sectors = []

    try:
        hot_stocks = fetcher.ths_hot_reason(today)
    except Exception:
        hot_stocks = []

    # 结合热点股和板块领涨股获取候选池
    candidates = {}
    if hot_stocks:
        for s in hot_stocks:
            candidates[s["code"]] = s

    # 从板块领涨股中补充
    if sector_data:
        for s in sector_data.get("top", []):
            leader_code = s.get("leader", "")
            if leader_code and leader_code not in candidates:
                try:
                    q = fetcher.tencent_quote([leader_code])
                    if leader_code in q:
                        candidates[leader_code] = {
                            "code": leader_code,
                            "name": q[leader_code].get("name", ""),
                            "close": q[leader_code].get("price", 0),
                            "zhangfu": q[leader_code].get("change_pct", 0),
                            "huanshou": q[leader_code].get("turnover_pct", 0),
                            "chengjiaoe": q[leader_code].get("amount_wan", 0) * 10000,
                            "reason": s.get("name", ""),
                        }
                except Exception:
                    pass

    if not candidates:
        return []

    # ── 第2步：获取实时行情（主力数据源） ──
    codes = list(candidates.keys())
    try:
        quotes = fetcher.tencent_quote(codes)
    except Exception:
        quotes = {}

    # ── 第3步：逐只筛选（用腾讯实时数据做判断） ──
    picked = []
    for code, stock in candidates.items():
        q = quotes.get(code, {})
        name = q.get("name", stock.get("name", ""))
        price = q.get("price", 0)
        change_pct = q.get("change_pct", 0)
        amount_wan = q.get("amount_wan", 0)
        turnover_pct = q.get("turnover_pct", 0)
        vol_ratio = q.get("vol_ratio", 1)
        reason_tags = stock.get("reason", "")

        # 过滤ST股
        import re as _re
        if _re.search(r'ST|退市', str(name)):
            continue

        # 涨幅过滤：>1% 但未涨停（明天还有空间）
        if change_pct < AfternoonPick.PRICE_CHANGE_MIN * 100 or change_pct > AfternoonPick.PRICE_CHANGE_MAX * 100:
            continue

        # 成交额过滤：>1亿（流动性）
        if amount_wan < AfternoonPick.TURNOVER_MIN / 10000:
            continue

        # 换手率过滤：3-25% 活跃度适中
        if turnover_pct < AfternoonPick.TURNOVER_RATE_MIN * 100 or turnover_pct > AfternoonPick.TURNOVER_RATE_MAX * 100:
            continue

        # ── 获取资金流向 ──
        try:
            fund_flow = fetcher.eastmoney_fund_flow_minute(code)
            if fund_flow:
                total_main_net = sum(f["main_net"] for f in fund_flow)
            else:
                total_main_net = 0
        except Exception:
            total_main_net = 0

        # 主力净流入过滤
        if total_main_net < AfternoonPick.MAIN_NET_INFLOW_MIN:
            continue

        # ── 均线确认 ──
        try:
            ma_status = fetcher.get_ma_status(code)
            trend_up = ma_status.get("trend_up", False)
        except Exception:
            trend_up = False

        # 评分
        score = 50
        if trend_up:
            score += 20
        if total_main_net > 1000_0000:  # 主力流入>1000万
            score += 15
        elif total_main_net > 500_0000:
            score += 10
        if amount_wan > 10_0000:  # 成交额>10亿
            score += 10
        if any(s in reason_tags for s in top_sectors):
            score += 10
        if vol_ratio > 1.2:
            score += 5

        # 选股理由
        reasons = []
        if total_main_net > 500_0000:
            reasons.append(f"主力净流入{total_main_net/1e4:.0f}万")
        if trend_up:
            reasons.append("均线多头")
        if amount_wan > 10_0000:
            reasons.append("成交额大")
        if top_sectors:
            reasons.append("板块强势")

        picked.append({
            "code": code,
            "name": name,
            "pick_price": round(price, 2),
            "pick_change": round(change_pct, 2),
            "turnover": amount_wan * 10000,
            "main_net_inflow": total_main_net,
            "tail_change": 0,  # 简化处理
            "sector": top_sectors[0] if top_sectors else "",
            "reason": " + ".join(reasons),
            "score": min(score, 100),
            "ma_status": trend_up,
            "fund_inflow": total_main_net,
        })

    # 排序：主力净流入优先 + 均线多头优先
    picked.sort(key=lambda x: (x["ma_status"], x["fund_inflow"]), reverse=True)
    results = picked[:AfternoonPick.PICK_COUNT]

    return results


# ════════════════════════════════════════════════════════════
# 三、自选股分析
# ════════════════════════════════════════════════════════════
def analyze_self_stock(code: str) -> dict:
    """
    分析单只自选股，返回买卖建议。
    """
    code = fetcher.normalize_code(code)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 获取完整画像 ──
    profile = fetcher.get_stock_profile(code)
    quote = profile.get("quote", {})
    ma_status = profile.get("ma_status", {})
    main_net = profile.get("main_net_inflow", 0)
    hot_reason = profile.get("hot_reason", "")

    # ── 各维度评分 ──

    # 1. 题材热度 (30%)
    theme_score = 0
    if hot_reason:
        tags = hot_reason.split("+")
        theme_score = min(len(tags) * 15, 30)

    # 2. 技术形态 (25%)
    tech_score = 0
    if ma_status.get("trend_up"):
        tech_score += 15
    if ma_status.get("ma5_above_ma10"):
        tech_score += 5
    if ma_status.get("ma10_above_ma20"):
        tech_score += 5
    tech_score = min(tech_score, 25)

    # 3. 资金流向 (20%)
    fund_score = 0
    if main_net > 2000_0000:
        fund_score = 20
    elif main_net > 1000_0000:
        fund_score = 15
    elif main_net > 500_0000:
        fund_score = 10
    elif main_net > 0:
        fund_score = 5

    # 4. 量价配合 (15%)
    vol_score = 0
    change_pct = quote.get("change_pct", 0)
    vol_ratio = quote.get("vol_ratio", 1)
    if vol_ratio > 1.5 and change_pct > 0:
        vol_score = 15
    elif vol_ratio > 1.2 and change_pct > 0:
        vol_score = 10
    elif vol_ratio > 1.0:
        vol_score = 5

    # 5. 风险控制 (10%)
    risk_score = 10
    if change_pct > 9.5:  # 接近涨停
        risk_score -= 5
    if quote.get("turnover_pct", 0) > 25:  # 换手率过高
        risk_score -= 3
    if code.startswith("3"):  # 创业板
        risk_score -= 0  # 中性

    total_score = theme_score + tech_score + fund_score + vol_score + risk_score

    # ── 买卖建议 ──
    price = quote.get("price", 0)

    if total_score >= 70:
        buy_advice = "✅ 可买"
    elif total_score >= 55:
        buy_advice = "⏳ 等待确认"
    else:
        buy_advice = "❌ 不建议"

    # 计算买卖区间
    buy_range_low = round(price * 0.96, 2) if price else 0
    buy_range_high = round(price * 1.02, 2) if price else 0
    target_price1 = round(price * 1.06, 2) if price else 0  # 第一目标 +6%
    target_price2 = round(price * 1.12, 2) if price else 0  # 第二目标 +12%
    stop_loss = round(price * 0.95, 2) if price else 0      # 止损 -5%

    # ── 分析依据 ──
    analysis_lines = []
    if hot_reason:
        analysis_lines.append(f"题材归因: {hot_reason}")
    if ma_status.get("trend_up"):
        analysis_lines.append(f"均线多头: MA5({ma_status.get('ma5',0):.2f}) > MA10({ma_status.get('ma10',0):.2f}) > MA20({ma_status.get('ma20',0):.2f})")
    else:
        analysis_lines.append(f"均线状态: 非多头排列 (MA5:{ma_status.get('ma5','-')} MA10:{ma_status.get('ma10','-')} MA20:{ma_status.get('ma20','-')})")
    if main_net > 0:
        analysis_lines.append(f"主力净流入: {main_net/1e4:.0f}万元")
    else:
        analysis_lines.append(f"主力净流出: {abs(main_net)/1e4:.0f}万元")
    if change_pct > 0:
        analysis_lines.append(f"当前涨幅: +{change_pct}%")
    else:
        analysis_lines.append(f"当前涨幅: {change_pct}%")

    score_detail = {
        "题材热度": round(theme_score, 1),
        "技术形态": round(tech_score, 1),
        "资金流向": round(fund_score, 1),
        "量价配合": round(vol_score, 1),
        "风险控制": round(risk_score, 1),
    }

    return {
        "analysis_date": today,
        "price": price,
        "score": round(total_score, 1),
        "score_detail": score_detail,
        "buy_advice": buy_advice,
        "buy_range_low": buy_range_low,
        "buy_range_high": buy_range_high,
        "target_price1": target_price1,
        "target_price2": target_price2,
        "stop_loss": stop_loss,
        "analysis_reason": "\n".join(analysis_lines),
        "ma_status": ma_status,
        "main_net_inflow": main_net,
        "hot_reason": hot_reason,
        "quote": quote,
    }


# ════════════════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import json

    print("=" * 50)
    print("开盘选股测试")
    print("=" * 50)
    picks = morning_pick()
    print(f"选出 {len(picks)} 只")
    for p in picks:
        print(f"  {p['code']} {p['name']} {p['pick_price']}元 {p['pick_change']}% | {p['reason']} | 评分:{p['score']}")

    print("\n" + "=" * 50)
    print("尾盘选股测试")
    print("=" * 50)
    picks = afternoon_pick()
    print(f"选出 {len(picks)} 只")
    for p in picks:
        print(f"  {p['code']} {p['name']} {p['pick_price']}元 {p['pick_change']}% | {p['reason']} | 评分:{p['score']}")

    print("\n" + "=" * 50)
    print("自选股分析测试")
    print("=" * 50)
    analysis = analyze_self_stock("600519")
    print(f"评分: {analysis['score']} | 建议: {analysis['buy_advice']}")
    print(f"买入区间: {analysis['buy_range_low']} - {analysis['buy_range_high']}")
    print(f"目标价: {analysis['target_price1']} / {analysis['target_price2']}")
    print(f"止损价: {analysis['stop_loss']}")
    print(f"分析依据:\n{analysis['analysis_reason']}")
