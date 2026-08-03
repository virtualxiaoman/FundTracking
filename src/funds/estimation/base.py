from abc import ABC, abstractmethod

from src.funds.fund_data import FundEstimation


class FundEstimationProvider(ABC):
    """
    基金估值数据源接口，一个Provider对应一个数据源。
    """

    @property
    @abstractmethod
    def source(self) -> str:
        """
        数据源名称。例如: eastmoney tencent
        """
        pass

    @abstractmethod
    def estimate(self, fund_code: str) -> FundEstimation:
        """
        获取基金实时估值
        成功: 返回 FundEstimation；失败: 抛出 FundError 子类异常
        """
        pass
