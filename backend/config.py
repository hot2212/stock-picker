"""
选股系统配置
===========
所有阈值和参数集中管理，自我优化模块会自动更新此文件中的数值。
"""

import os

# ============================================================
# 一、项目路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "picker.db")

# ============================================================
# 二、开盘选股参数（9:27）
# ============================================================
class MorningPick:
    # --- 竞价条件 ---
    COMPETITION_AMOUNT_MIN = 800_0000        # 竞价最低金额（元）
    COMPETITION_CHANGE_MIN = 0.02           # 竞价最低涨幅（2%）
    COMPETITION_CHANGE_MAX = 0.06           # 竞价最高涨幅（6%）
    COMPETITION_VOL_RATIO_MIN = 2.0         # 竞价量比最小值

    # --- 盘面条件 ---
    MARKET_VALUE_MIN = 50_0000_0000          # 流通市值下限（50亿）
    MARKET_VALUE_MAX = 500_0000_0000         # 流通市值上限（500亿）
    TURNOVER_MIN = 3_0000_0000              # 成交额下限（3亿）
    TURNOVER_RATE_MIN = 0.03                # 换手率下限（3%）
    TURNOVER_RATE_MAX = 0.20                # 换手率上限（20%）
    VOL_RATIO_MIN = 1.5                     # 量比最小值

    # --- 技术面 ---
    PRICE_CHANGE_MIN = 0.02                 # 涨幅下限（2%）
    PRICE_CHANGE_MAX = 0.08                 # 涨幅上限（8%）

    # --- 板块 ---
    SECTOR_RANK_TOP_N = 5                   # 板块排名前N

    # --- 选股数量 ---
    PICK_COUNT = 5                          # 选股数量

# ============================================================
# 三、尾盘选股参数（14:30）
# ============================================================
class AfternoonPick:
    # --- 盘面条件 ---
    PRICE_CHANGE_MIN = 0.01                 # 当日涨幅下限（1%）
    PRICE_CHANGE_MAX = 0.05                 # 当日涨幅上限（5%）
    TAIL_CHANGE_MIN = 0.005                 # 14:00-14:30 涨幅 > 0.5%
    TURNOVER_MIN = 3_0000_0000              # 成交额下限（3亿）
    TURNOVER_RATE_MIN = 0.03                # 换手率下限（3%）
    TURNOVER_RATE_MAX = 0.25                # 换手率上限（25%）

    # --- 资金面 ---
    MAIN_NET_INFLOW_MIN = 500_0000          # 主力净流入下限（500万）

    # --- 趋势 ---
    SECTOR_RANK_TOP_N = 10                  # 板块排名前N

    # --- 选股数量 ---
    PICK_COUNT = 5

# ============================================================
# 四、自选股评分权重
# ============================================================
class ScoreWeights:
    THEME_HOT = 0.30        # 题材热度
    TECH_FORM = 0.25        # 技术形态
    FUND_FLOW = 0.20        # 资金流向
    VOL_PRICE = 0.15        # 量价配合
    RISK_CTRL = 0.10        # 风险控制

# ============================================================
# 五、定时任务
# ============================================================
class Schedule:
    MORNING_PICK_TIME = "09:27"             # 开盘选股时间
    AFTERNOON_PICK_TIME = "14:30"           # 尾盘选股时间
    CLOSE_RECORD_TIME = "15:00"             # 收盘记录时间
    REALTIME_INTERVAL_SECONDS = 30          # 实时行情刷新间隔（秒）
    SECTOR_INTERVAL_MINUTES = 5             # 板块排名刷新间隔（分钟）
    THEME_INTERVAL_MINUTES = 30             # 题材热度刷新间隔（分钟）
    AUTO_OPTIMIZE_DAY = "sat,sun"           # 自动优化运行日
    AUTO_OPTIMIZE_TIME = "10:00"            # 自动优化运行时间

# ============================================================
# 六、数据保留
# ============================================================
class DataRetention:
    PICK_RECORD_DAYS = 30                   # 选股记录保留天数
    CLEANUP_DAY = 1                         # 每月1日清理

# ============================================================
# 七、自我优化范围（各参数的搜索区间）
# ============================================================
class OptimizeRange:
    COMPETITION_AMOUNT = [300_0000, 500_0000, 800_0000, 1000_0000, 1500_0000]
    COMPETITION_CHANGE_MIN = [0.01, 0.015, 0.02, 0.025, 0.03]
    COMPETITION_CHANGE_MAX = [0.05, 0.06, 0.07, 0.08]
    TURNOVER_MIN = [1_0000_0000, 2_0000_0000, 3_0000_0000, 5_0000_0000]
    MAIN_NET_INFLOW_MIN = [200_0000, 300_0000, 500_0000, 800_0000]


# ============================================================
# 工具：动态更新配置值
# ============================================================
def update_config(section: str, param: str, value):
    """
    自我优化模块调用此函数来更新配置。
    section: 类名，如 "MorningPick"
    param: 参数名，如 "COMPETITION_AMOUNT_MIN"
    value: 新值
    """
    cls_map = {
        "MorningPick": MorningPick,
        "AfternoonPick": AfternoonPick,
        "ScoreWeights": ScoreWeights,
    }
    cls = cls_map.get(section)
    if cls and hasattr(cls, param):
        setattr(cls, param, value)
        return True
    return False
