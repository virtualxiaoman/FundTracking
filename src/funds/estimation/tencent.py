from __future__ import annotations

from datetime import datetime

import requests

from src.funds.estimation.base import FundEstimationProvider
from src.funds.exceptions import FundEstimationProviderError, FundNotFoundError, FundEstimationParseError
from src.funds.fund_data import FundEstimation


class TencentEstimationProvider(FundEstimationProvider):
    URL = "https://qt.gtimg.cn/q=fund{fund_code}"

    @property
    def source(self) -> str:
        return "tencent"

    def estimate(self, fund_code: str) -> FundEstimation:
        try:
            response = requests.get(self.URL.format(fund_code=fund_code), timeout=5)
            response.encoding = "gbk"
        except Exception as e:
            raise FundEstimationProviderError(source=self.source, fund_code=fund_code, original_error=e)

        text = response.text.strip()
        if not text:
            raise FundNotFoundError(fund_code)
        try:
            data = self._parse_response(text)
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=text,
                                           message=f"tencent parse error: {e}")
        try:
            estimate_nav = float(data["nav"])
            change_rate = float(data["change"]) / 100
            # update_time = datetime.now()
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=data,
                                           message=f"tencent field error: {e}")
        return FundEstimation(fund_code=fund_code, source=self.source, query_time=datetime.now(),
                              estimate_nav=estimate_nav, change_rate=change_rate)

    def _parse_response(self, text: str) -> dict:
        """
        腾讯返回: v_fund000001="xxx~xxx~xxx" 不同接口字段可能变化。 这里保留解析入口。
        """
        if "=" not in text:
            raise ValueError("invalid tencent response")
        raw = (text.split("=")[1].strip('";'))
        fields = raw.split("~")
        # 这里根据腾讯字段调整，当前作为备用实现结构
        return {"nav": fields[1], "change": fields[3], }
