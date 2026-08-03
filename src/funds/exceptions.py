from __future__ import annotations

from typing import Optional


class FundError(Exception):
    """
    基金模块基础异常

    所有基金相关异常的父类。
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class FundNotFoundError(FundError):
    """
    基金不存在异常

    特点:
    - 属于确定性错误
    - 不应该触发数据源fallback
    - 前端通常返回404
    """

    def __init__(self, fund_code: str, message: Optional[str] = None):
        self.fund_code = fund_code

        if message is None:
            message = f"基金不存在: {fund_code}"

        super().__init__(message)


class FundEstimationError(FundError):
    """
    基金估值相关异常基类

    包括:
    - 数据源请求失败
    - 数据解析失败
    - 数据格式错误
    """


class FundEstimationProviderError(FundEstimationError):
    """
    基金估值数据源异常

    例如:
    - 网络错误
    - 请求超时
    - HTTP错误
    - 数据源不可用

    Repository遇到这个异常:
        可以fallback到其他provider
    """

    def __init__(
            self,
            source: str,
            fund_code: str,
            message: Optional[str] = None,
            original_error: Optional[Exception] = None
    ):
        self.source = source
        self.fund_code = fund_code
        self.original_error = original_error

        if message is None:
            message = (
                f"基金估值数据源异常: "
                f"source={source}, fund={fund_code}"
            )

        super().__init__(message)


class FundEstimationParseError(FundEstimationError):
    """
    基金估值解析异常

    例如:
    - 接口返回字段缺失
    - 数字转换失败
    - 时间格式错误

    是否fallback:
        可以fallback

    因为:
        当前数据源异常，不代表基金不存在
    """

    def __init__(
            self,
            source: str,
            fund_code: str,
            raw_data=None,
            message: Optional[str] = None
    ):
        self.source = source
        self.fund_code = fund_code
        self.raw_data = raw_data

        if message is None:
            message = (
                f"基金估值解析失败: "
                f"source={source}, fund={fund_code}"
            )

        super().__init__(message)


class FundEstimationUnavailableError(FundEstimationError):
    """
    所有估值来源均不可用

    例如:

        EastMoney失败
        Tencent失败

    Repository最终抛出此异常。
    """

    def __init__(
            self,
            fund_code: str,
            errors: list[Exception]
    ):
        self.fund_code = fund_code
        self.errors = errors

        message = (
            f"基金估值暂不可用: {fund_code}, "
            f"failed providers={len(errors)}"
        )

        super().__init__(message)
