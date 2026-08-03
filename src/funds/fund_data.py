from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True, frozen=True)
class FundData:
    """基金"""
    code: str
    name: str

    def __str__(self) -> str:
        return f"[{self.code}]: {self.name}"


@dataclass(slots=True)
class FundListCache:
    update_date: date
    funds: list[FundData]


@dataclass(slots=True)
class FundHistoryItem:
    """单日基金净值数据"""
    date: date
    unit_nav: float  # 单位净值
    accumulated_nav: float  # 累积净值
    daily_change: float  # 日涨跌幅(原始值，如 0.0125 表示 +1.25%)


@dataclass(slots=True)
class FundHistoryCache:
    """基金历史数据缓存"""
    update_date: date  # 缓存更新日期
    fund_code: str  # 基金代码
    items: list[FundHistoryItem]  # 按日期升序排列（最早 -> 最新）


@dataclass(slots=True, frozen=True)
class FundEstimation:
    """基金实时估值"""
    fund_code: str
    estimate_nav: float  # 当前估算净值
    change_rate: float  # 估算涨跌幅(原始值，如 0.0125 表示 +1.25%)
    query_time: datetime  # 查询接口的时间
    source: str = "eastmoney"
