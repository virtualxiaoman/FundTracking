from __future__ import annotations

from datetime import datetime

import requests

from src.funds.estimation.base import FundEstimationProvider
from src.funds.exceptions import FundEstimationProviderError, FundEstimationParseError, FundNotFoundError
from src.funds.fund_data import FundEstimation


class CftaoEstimationProvider(FundEstimationProvider):
    """
    CFTAO 基金估值数据源
    接口: https://jj.cftao.com/api/fund/info/{fund_code}
    返回: 实时估算净值
    source: cftao
    """

    URL = "https://jj.cftao.com/api/fund/info/{fund_code}"

    @property
    def source(self) -> str:
        return "cftao"

    def estimate(self, fund_code: str) -> FundEstimation:
        # ============================
        # 1. 请求接口
        # ============================
        try:
            response = requests.get(self.URL.format(fund_code=fund_code), timeout=5)
            response.raise_for_status()
        except Exception as e:
            raise FundEstimationProviderError(source=self.source, fund_code=fund_code, original_error=e,
                                              message=f"cftao request failed: {e}")

        # ============================
        # 2. 解析JSON
        # ============================
        try:
            result = response.json()
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=response.text,
                                           message=f"cftao json parse failed: {e}")

        # ============================
        # 3. 判断接口状态
        # ============================
        if not result.get("success"):
            raise FundNotFoundError(fund_code, message=f"fund not found or unavailable: {fund_code}")
        data = result.get("data")
        if not data:
            raise FundNotFoundError(fund_code)

        # ============================
        # 4. 字段解析
        # ============================
        try:
            estimate_nav = float(data["gsz"])
            change_rate = float(data["gszzl"]) / 100
            # update_time = datetime.strptime(data["gztime"], "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=data,
                                           message=f"cftao field parse failed: {e}")

        # ============================
        # 5. 返回估值对象
        # ============================

        return FundEstimation(fund_code=fund_code, source=self.source, query_time=datetime.now(),
                              estimate_nav=estimate_nav, change_rate=change_rate)


if __name__ == "__main__":
    provider = CftaoEstimationProvider()
    fund_code = "000001"  # 替换为你想查询的基金代码
    try:
        estimation = provider.estimate(fund_code)
        print(estimation)
    except Exception as e:
        print(f"Error: {e}")
