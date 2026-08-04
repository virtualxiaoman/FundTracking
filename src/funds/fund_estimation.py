from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Iterable

from src.funds.estimation.base import FundEstimationProvider
from src.funds.estimation.cftao import CftaoEstimationProvider
from src.funds.estimation.eastmoney import EastMoneyEstimationProvider
from src.funds.estimation.sina import SinaEstimationProvider
from src.funds.estimation.tencent import TencentEstimationProvider
from src.funds.exceptions import FundNotFoundError, FundEstimationError, FundEstimationUnavailableError
from src.funds.fund_data import FundEstimation


class FundEstimationRepository:
    """
    基金实时估值仓库

    负责:
    - provider管理
    - 默认source
    - source切换
    - 缓存
    - force刷新
    - 多基金并发获取
    """

    def __init__(self, providers: list[FundEstimationProvider], default_source: str = "eastmoney",
                 cache_seconds: int = 60):
        """
        缓存: key: (fund_code, source), value: FundEstimation
        例如:
        {
            (
                "000001",
                "eastmoney"
            ):
                FundEstimation(...)
        }
        Args:
            providers:
                所有支持的数据源

            default_source:
                默认优先数据源

            cache_seconds:
                缓存有效时间
        """

        self.providers: dict[str, FundEstimationProvider] = {provider.source: provider for provider in providers}
        if default_source not in self.providers:
            raise ValueError(f"unknown default source: {default_source}")
        self.default_source = default_source
        self.cache_seconds = cache_seconds
        self._cache: dict[tuple[str, str], FundEstimation] = {}

    def get_estimation(self, fund_code: str, force: bool = False, source: str | None = None) -> FundEstimation:
        """
        获取单个基金估值
        Args:
            fund_code:
                基金代码

            force:
                True: 强制请求数据源
                False: 优先使用缓存

            source:
                指定数据源
                None: 使用默认source并自动fallback

        Returns:
            FundEstimation

        Raises:
            FundNotFoundError:
                基金不存在
            FundEstimationUnavailableError:
                所有数据源失败
        """
        providers = self._get_provider_chain(source)
        errors: list[Exception] = []
        for provider in providers:
            cache_key = (fund_code, provider.source)
            cached = self._cache.get(cache_key)

            # ===============================
            # 1. 查询缓存
            # ===============================
            if not force and self._cache_valid(cached):
                print(f"cache hit: {fund_code} @ {provider.source}")
                return cached

            # ===============================
            # 2. 请求provider
            # ===============================

            try:
                estimation = provider.estimate(fund_code)
                self._cache[cache_key] = estimation  # 更新缓存
                print(f"cache update: {fund_code} @ {provider.source}")
                return estimation

            except FundNotFoundError as e:
                raise FundNotFoundError(fund_code, message=f"基金不存在: 这是确定错误 不应该继续请求其他source。{e}")
            except FundEstimationError as e:
                """ 数据源异常: 允许fallback 但是不修改缓存 """
                errors.append(e)
                """ 如果以前成功过: 返回旧数据 注意: 不更新时间 """
                if cached is not None:
                    return cached
        raise FundEstimationUnavailableError(fund_code, errors)

    def get_estimations(self, fund_codes: Iterable[str], force: bool = False, source: str | None = None,
                        max_workers: int = 16) -> dict[str, FundEstimation]:
        """
        批量获取基金估值 使用线程池并发。
        Args:
            fund_codes:
                基金代码列表
            force:
                是否强制刷新
            source:
                指定数据源
            max_workers:
                最大线程数
        Returns:
            {
                "000001":
                    FundEstimation(...)
            }
        注意: 单个基金失败不会影响其他基金。
        """
        result: dict[str, FundEstimation] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks = {executor.submit(self.get_estimation, code, force, source): code for code in fund_codes}

            for future in as_completed(tasks):
                code = tasks[future]
                try:
                    result[code] = future.result()
                except Exception:
                    """ 单个失败忽略 如果需要详细错误: 可以后续增加: get_estimations_with_errors() """
                    continue

        return result

    def clear_cache(self, fund_code: str | None = None, source: str | None = None):
        """
        清理缓存
        Examples:
        清理全部:
            clear_cache()
        清理基金:
            clear_cache(
                "000001"
            )
        清理指定source:
            clear_cache(
                source="eastmoney"
            )
        """

        if fund_code is None and source is None:
            self._cache.clear()
            return

        remove_keys = []
        for code, src in self._cache:
            if fund_code is not None and code != fund_code:
                continue
            if source is not None and src != source:
                continue
            remove_keys.append((code, src))

        for key in remove_keys:
            self._cache.pop(key, None)

    def _get_provider_chain(self, source: str | None) -> list[FundEstimationProvider]:
        """
        获取provider执行顺序
        source=None:
            eastmoney
                |
                tencent
        source="tencent":
            tencent
        """

        if source is not None:
            if source not in self.providers: raise ValueError(f"unknown source: {source}")
            return [self.providers[source]]

        result = []
        # 默认source优先
        result.append(self.providers[self.default_source])
        # 其他source作为fallback
        for name, provider in self.providers.items():
            if name != self.default_source:
                result.append(provider)
        return result

    def _cache_valid(self, estimation: FundEstimation | None) -> bool:
        """
        判断缓存是否有效
        """
        if estimation is None:
            return False
        return datetime.now() - estimation.query_time < timedelta(seconds=self.cache_seconds)


if __name__ == "__main__":
    repo = FundEstimationRepository(
        providers=[
            CftaoEstimationProvider(),
            SinaEstimationProvider(),
            EastMoneyEstimationProvider(),
            TencentEstimationProvider(),
        ],
        default_source="cftao",
        cache_seconds=30
    )
    res = repo.get_estimation("000001")
    print(res.change_rate)
    res = repo.get_estimation("000001")
    print(res.change_rate)
