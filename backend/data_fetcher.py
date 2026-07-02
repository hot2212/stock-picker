"""
数据采集模块
===========
封装所有数据源接口，统一返回格式。
数据源优先级：腾讯(高频) > 同花顺 > 东财(限流) > 百度
"""

import time
import random
import json
import urllib.request
import requests
import pandas as pd
from datetime import datetime, date
from typing import Optional


# ── 全局配置 ──────────────────────────────────────────────
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

# 东财防封：全局节流 + 会话复用
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0
_em_last_call = [0.0]


def em_get(url: str, params: dict = None, headers: dict = None, timeout: int = 15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.3))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()


# ── 股票代码前缀处理 ──────────────────────────────────────
def get_prefix(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    return "sz"


def normalize_code(code: str) -> str:
    """归一化为6位数字"""
    code = code.strip().upper()
    for suffix in [".SH", ".SZ", ".BJ"]:
        if code.endswith(suffix):
            code = code[:-3]
    for prefix in ["SH", "SZ", "BJ"]:
        if code.startswith(prefix):
            code = code[2:]
    return code


# ════════════════════════════════════════════════════════════
# 1. 腾讯实时行情（高频，不封IP）
# ════════════════════════════════════════════════════════════
def tencent_quote(codes: list) -> dict:
    """
    批量拉取腾讯财经实时行情。
    返回: {code: {name, price, change_pct, amount_wan, turnover_pct, vol_ratio, ...}}
    """
    prefixed = []
    for c in codes:
        c = normalize_code(str(c))
        prefixed.append(f"{get_prefix(c)}{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "code": code,
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "amplitude_pct": float(vals[43]) if vals[43] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
        }
    return result


# ════════════════════════════════════════════════════════════
# 2. 同花顺热点 — 当日强势股 + 题材归因
# ════════════════════════════════════════════════════════════
def ths_hot_reason(date_str: str = None) -> list:
    """
    同花顺当日强势股归因，返回题材标签。
    返回: [{code, name, 涨幅%, 题材归因, 换手率%, 成交额, 大单净量, ...}]
    """
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date_str}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {"User-Agent": UA}
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")

    rows = data.get("data") or []
    result = []
    for item in rows:
        result.append({
            "code": item.get("code", ""),
            "name": item.get("name", ""),
            "close": item.get("close", 0),
            "zhangfu": item.get("zhangfu", 0),
            "huanshou": item.get("huanshou", 0),
            "chengjiaoe": item.get("chengjiaoe", 0),
            "chengjiaoliang": item.get("chengjiaoliang", 0),
            "ddejingliang": item.get("ddejingliang", 0),
            "reason": item.get("reason", ""),
            "market": item.get("market", ""),
        })
    return result


def get_hot_themes(stocks: list = None) -> dict:
    """
    从同花顺热点数据中提取热门题材。
    返回: {theme: {count, avg_zhangfu, stocks: [...]}, ...}
    """
    if stocks is None:
        stocks = ths_hot_reason()

    theme_map = {}
    for s in stocks:
        reasons = str(s.get("reason", "")).split("+")
        for r in reasons:
            r = r.strip()
            if not r or r == "nan":
                continue
            if r not in theme_map:
                theme_map[r] = {"count": 0, "total_zhangfu": 0, "stocks": []}
            theme_map[r]["count"] += 1
            theme_map[r]["total_zhangfu"] += float(s.get("zhangfu", 0) or 0)
            theme_map[r]["stocks"].append(s["name"])

    # 按股票数量排序
    sorted_themes = sorted(theme_map.items(), key=lambda x: -x[1]["count"])
    result = {}
    for theme, data in sorted_themes:
        avg_zhangfu = round(data["total_zhangfu"] / data["count"], 2) if data["count"] > 0 else 0
        result[theme] = {
            "count": data["count"],
            "avg_zhangfu": avg_zhangfu,
            "stocks": data["stocks"][:5],  # 每题材最多5只代表股
        }
    return result


# ════════════════════════════════════════════════════════════
# 3. 东财行业板块排名
# ════════════════════════════════════════════════════════════
def industry_comparison(top_n: int = 20) -> dict:
    """
    全行业涨跌幅排名。
    返回: {top: [{rank, name, change_pct, up_count, down_count, leader, leader_change}], bottom: [...]}
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    headers = {"User-Agent": UA}
    r = em_get(url, params=params, headers=headers, timeout=15)
    d = r.json()
    items = d.get("data", {}).get("diff", [])
    if not items:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": item.get("f3", 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })

    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:] if len(rows) > top_n else [],
        "total": len(rows),
    }


# ════════════════════════════════════════════════════════════
# 4. 东财push2个股资金流向（分钟级）
# ════════════════════════════════════════════════════════════
def eastmoney_fund_flow_minute(code: str) -> list:
    """
    个股资金流向（分钟级，当日盘中）。
    返回: [{time, main_net, small_net, mid_net, large_net, super_net}, ...]
    单位: 元
    """
    code = normalize_code(code)
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }
    try:
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
    except Exception:
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time": parts[0],
                "main_net": float(parts[1]),
                "small_net": float(parts[2]),
                "mid_net": float(parts[3]),
                "large_net": float(parts[4]),
                "super_net": float(parts[5]),
            })
    return rows


# ════════════════════════════════════════════════════════════
# 5. 百度K线 — 带MA5/MA10/MA20
# ════════════════════════════════════════════════════════════
def baidu_kline_with_ma(code: str, start_time: str = "") -> dict:
    """
    百度股市通K线，返回带ma5/ma10/ma20均价。
    """
    code = normalize_code(code)
    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    result = d.get("Result", {})
    md = result.get("newMarketData", {})
    keys = md.get("keys", [])
    market_data = md.get("marketData", "")

    klines = []
    if market_data:
        for line in market_data.split(";"):
            if not line.strip():
                continue
            vals = line.split(",")
            if len(vals) >= 10:
                kline = {}
                for i, k in enumerate(keys):
                    if i < len(vals):
                        kline[k] = vals[i]
                klines.append(kline)

    return {"keys": keys, "klines": klines, "code": code}


def get_ma_status(code: str) -> dict:
    """
    获取股票均线状态，判断趋势。
    返回: {ma5, ma10, ma20, trend_up(是否多头), close, ...}
    """
    data = baidu_kline_with_ma(code)
    klines = data.get("klines", [])
    if not klines:
        return {"trend_up": False, "error": "no_data"}

    last = klines[-1]
    try:
        close = float(last.get("close", 0))
        ma5 = float(last.get("ma5avgprice", 0)) if "ma5avgprice" in last else None
        ma10 = float(last.get("ma10avgprice", 0)) if "ma10avgprice" in last else None
        ma20 = float(last.get("ma20avgprice", 0)) if "ma20avgprice" in last else None

        trend_up = False
        if ma5 and ma10 and ma20:
            trend_up = close > ma5 > ma10 > ma20

        # 最近5日成交量均值
        volumes = []
        for k in klines[-5:]:
            v = float(k.get("volume", 0))
            volumes.append(v)
        avg_vol_5 = sum(volumes) / len(volumes) if volumes else 0

        # 当日成交量
        today_vol = float(last.get("volume", 0))

        return {
            "close": close,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "trend_up": trend_up,
            "ma5_above_ma10": ma5 > ma10 if ma5 and ma10 else False,
            "ma10_above_ma20": ma10 > ma20 if ma10 and ma20 else False,
            "today_vol": today_vol,
            "avg_vol_5": avg_vol_5,
            "vol_ratio_ma5": today_vol / avg_vol_5 if avg_vol_5 > 0 else 0,
        }
    except (ValueError, IndexError):
        return {"trend_up": False, "error": "parse_error"}


# ════════════════════════════════════════════════════════════
# 6. 竞价数据（通过腾讯行情获取）
# ════════════════════════════════════════════════════════════
def get_competition_data(codes: list) -> dict:
    """
    获取集合竞价数据。
    9:25后调用，通过腾讯行情获取开盘价、竞价量等信息。
    返回: {code: {open, competition_amount, competition_change, ...}}
    """
    quotes = tencent_quote(codes)
    result = {}
    for code, q in quotes.items():
        if q["last_close"] > 0:
            competition_change = round((q["open"] - q["last_close"]) / q["last_close"] * 100, 2)
        else:
            competition_change = 0

        # 竞价金额 ≈ 开盘时段的成交额（腾讯amount_wan是全天的，这里只能估算）
        # 更准确的竞价量需要通达信接口
        result[code] = {
            "code": code,
            "name": q["name"],
            "open": q["open"],
            "last_close": q["last_close"],
            "competition_change": competition_change,
            "price": q["price"],
            "change_pct": q["change_pct"],
            "amount_wan": q["amount_wan"],
            "turnover_pct": q["turnover_pct"],
            "vol_ratio": q["vol_ratio"],
            "mcap_yi": q["float_mcap_yi"],
        }
    return result


# ════════════════════════════════════════════════════════════
# 7. 综合查询 — 获取单只股票的完整画像
# ════════════════════════════════════════════════════════════
def get_stock_profile(code: str) -> dict:
    """
    获取单只股票的完整数据画像（用于自选股分析）。
    包含：实时行情、均线状态、资金流向、板块归属、题材归因。
    """
    code = normalize_code(code)
    profile = {"code": code}

    # 实时行情
    quotes = tencent_quote([code])
    if code in quotes:
        profile["quote"] = quotes[code]
    else:
        profile["quote"] = {}

    # 均线状态
    profile["ma_status"] = get_ma_status(code)

    # 资金流向
    fund_flow = eastmoney_fund_flow_minute(code)
    if fund_flow:
        total_main = sum(f["main_net"] for f in fund_flow)
        profile["main_net_inflow"] = total_main
        profile["fund_flow_count"] = len(fund_flow)
    else:
        profile["main_net_inflow"] = 0
        profile["fund_flow_count"] = 0

    # 题材归因（从同花顺热点中查找）
    try:
        hot_stocks = ths_hot_reason()
        for s in hot_stocks:
            if s["code"] == code:
                profile["hot_reason"] = s.get("reason", "")
                profile["hot_zhangfu"] = s.get("zhangfu", 0)
                break
        else:
            profile["hot_reason"] = ""
    except Exception:
        profile["hot_reason"] = ""

    return profile


# ════════════════════════════════════════════════════════════
# 8. 获取大盘指数
# ════════════════════════════════════════════════════════════
def get_market_index():
    """获取主要指数行情"""
    codes = ["000001", "000300", "399006", "000688"]
    quotes = tencent_quote(codes)
    return {
        "sh": quotes.get("000001", {}),      # 上证
        "hs300": quotes.get("000300", {}),    # 沪深300
        "cyb": quotes.get("399006", {}),      # 创业板
        "kc50": quotes.get("000688", {}),     # 科创50
    }


# ════════════════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 测试腾讯行情
    q = tencent_quote(["600519", "000001", "300059"])
    print("=== 腾讯行情 ===")
    for code, d in q.items():
        print(f"{d['name']}({code}): {d['price']}元 {d['change_pct']}%")

    # 测试板块排名
    print("\n=== 板块排名 ===")
    ind = industry_comparison(5)
    for r in ind["top"][:5]:
        print(f"{r['rank']}. {r['name']}: {r['change_pct']}%")

    # 测试同花顺热点
    print("\n=== 同花顺热点 ===")
    hot = ths_hot_reason()
    for s in hot[:5]:
        print(f"{s['name']}({s['code']}): {s['zhangfu']}% 题材: {s['reason']}")

    # 测试题材聚合
    themes = get_hot_themes(hot)
    print("\n=== 热门题材TOP10 ===")
    for i, (theme, d) in enumerate(list(themes.items())[:10]):
        print(f"{i+1}. {theme}: {d['count']}只股票 均涨幅{d['avg_zhangfu']}%")

    # 测试百度K线
    ma = get_ma_status("600519")
    print(f"\n=== 均线状态 ===")
    print(f"MA5={ma.get('ma5')} MA10={ma.get('ma10')} MA20={ma.get('ma20')}")
    print(f"趋势向上: {ma['trend_up']}")
