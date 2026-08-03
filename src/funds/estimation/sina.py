from __future__ import annotations

from datetime import datetime

import requests

from src.funds.estimation.base import FundEstimationProvider
from src.funds.exceptions import FundEstimationProviderError, FundEstimationParseError, FundNotFoundError
from src.funds.fund_data import FundEstimation


class SinaEstimationProvider(FundEstimationProvider):
    """
    新浪基金实时估值Provider
    API: https://stock.finance.sina.com.cn/fundInfo/api/openapi.php/FdFundService.getEstimateNetworthPic?symbol={code}
    数据:
    networth最后一条:
        min_time
        pre_nav
        growthrate
    返回:
        FundEstimation
    """

    URL = "https://stock.finance.sina.com.cn/fundInfo/api/openapi.php/FdFundService.getEstimateNetworthPic?symbol={fund_code}"

    @property
    def source(self) -> str:
        return "sina"

    def estimate(self, fund_code: str) -> FundEstimation:
        # ============================
        # 请求
        # ============================
        try:
            response = requests.get(self.URL.format(fund_code=fund_code), timeout=5)
            response.raise_for_status()
        except Exception as e:
            raise FundEstimationProviderError(source=self.source, fund_code=fund_code, original_error=e,
                                              message=f"sina request failed: {e}")

        # ============================
        # JSON解析
        # ============================
        try:
            result = response.json()
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=response.text,
                                           message=f"sina json parse failed: {e}")

        # ============================
        # 状态检查
        # ============================
        try:
            status_code = (result["result"]["status"]["code"])
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=result,
                                           message=f"sina status parse failed: {e}")

        if status_code != 0:
            raise FundNotFoundError(fund_code, message=f"sina fund unavailable: {fund_code}")

        # ============================
        # 获取data
        # ============================
        try:
            data = result["result"]["data"]
            networth = data["networth"]
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=result,
                                           message=f"sina data missing: {e}")
        if not networth:
            raise FundNotFoundError(fund_code, message=f"sina no networth data: {fund_code}")

        # ============================
        # 取最后一条估值
        # ============================
        try:
            latest = networth[-1]
            estimate_nav = float(latest["pre_nav"])
            change_rate = float(latest["growthrate"])
            # update_time = datetime.strptime((latest["pre_date"] + " " + latest["min_time"]), "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=latest,
                                           message=f"sina field parse failed: {e}")

        return FundEstimation(fund_code=fund_code, source=self.source, query_time=datetime.now(),
                              estimate_nav=estimate_nav, change_rate=change_rate)
