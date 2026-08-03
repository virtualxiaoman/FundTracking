from src.funds.estimation.eastmoney import EastMoneyEstimationProvider
from src.funds.estimation.tencent import TencentEstimationProvider
from src.funds.exceptions import FundNotFoundError, FundError


def test_eastmoney():
    provider = EastMoneyEstimationProvider()

    result = provider.estimate(
        "000001"
    )

    print(result)

    assert result.source == "eastmoney"
    assert result.fund_code == "000001"

    assert result.estimate_nav > 0


def test_tencent():
    provider = TencentEstimationProvider()

    result = provider.estimate(
        "000001"
    )

    print(result)

    assert result.source == "tencent"


def test_not_found():
    provider = EastMoneyEstimationProvider()

    try:

        provider.estimate(
            "999999"
        )


    except FundNotFoundError as e:

        print(
            "基金不存在:",
            e
        )


    else:

        raise AssertionError(
            "应该抛出FundNotFoundError"
        )


def test_provider_error():
    provider = EastMoneyEstimationProvider()

    try:

        provider.estimate(
            "000001"
        )


    except FundError as e:

        print(
            type(e).__name__,
            e
        )


if __name__ == "__main__":
    test_eastmoney()
    test_tencent()
    test_not_found()
    test_provider_error()
