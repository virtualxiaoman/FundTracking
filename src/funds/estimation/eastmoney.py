from __future__ import annotations

import json
import re
from datetime import datetime

import requests

from src.funds.estimation.base import FundEstimationProvider
from src.funds.exceptions import FundEstimationProviderError, FundNotFoundError, FundEstimationParseError
from src.funds.fund_data import FundEstimation


class EastMoneyEstimationProvider(FundEstimationProvider):
    URL = "http://fundgz.1234567.com.cn/js/{fund_code}.js"

    @property
    def source(self) -> str:
        return "eastmoney"

    def estimate(self, fund_code: str) -> FundEstimation:
        try:
            response = requests.get(self.URL.format(fund_code=fund_code), timeout=5)
        except Exception as e:
            raise FundEstimationProviderError(source=self.source, fund_code=fund_code, original_error=e)

        text = response.text.strip()
        if not text:
            raise FundNotFoundError(fund_code)

        try:
            data = self._parse_response(text)
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=text,
                                           message=f"eastmoney parse error: {e}")

        if not data.get("gsz"):
            raise FundNotFoundError(fund_code)

        try:
            estimate_nav = float(data["gsz"])
            change_rate = float(data["gszzl"]) / 100
            # update_time = datetime.strptime(data["gztime"], "%Y-%m-%d %H:%M")
        except Exception as e:
            raise FundEstimationParseError(source=self.source, fund_code=fund_code, raw_data=data,
                                           message=f"eastmoney field parse error: {e}")
        return FundEstimation(fund_code=fund_code, source=self.source, query_time=datetime.now(),
                              estimate_nav=estimate_nav, change_rate=change_rate)

    def _parse_response(self, text: str) -> dict:
        """
        解析: jsonpgz({...}) 为dict
        """
        match = re.search(r"jsonpgz\((.*)\)", text)
        if not match: raise ValueError("invalid response format")
        return json.loads(match.group(1))
