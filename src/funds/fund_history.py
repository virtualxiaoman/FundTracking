from __future__ import annotations

import pickle
from datetime import date, datetime, timedelta
from pathlib import Path

import akshare as ak

from src.config.path import FUNDS_DIR
from src.funds.fund_data import FundData, FundHistoryCache
from src.funds.fund_info import FundInfoRepository


class FundHistoryRepository:
    """
    基金历史净值仓库

    负责：
    - 基金历史净值查询
    - 历史数据缓存
    - 基金历史数据更新

    不负责：
    - 收益计算
    - 数据分析
    - DataFrame转换
    """

    def __init__(self):
        self.history_dir = FUNDS_DIR / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # =========================
    # 查询接口
    # =========================

    def get_history(
            self,
            fund_code: str,
            start: date | None = None,
            end: date | None = None,
            auto_update: bool = True,
    ) -> FundHistoryCache:
        """
        查询指定基金历史数据

        Args:
            fund_code:
                基金代码

            start:
                开始日期，None表示不限

            end:
                结束日期，None表示不限

            auto_update:
                是否自动检查并更新缓存

        Returns:
            FundHistoryCache
        """

        if auto_update:
            self._ensure_updated(fund_code)

        cache = self._load_cache(fund_code)

        if cache is None:
            raise FileNotFoundError(f"基金 {fund_code} 没有历史数据，请先更新")

        items = cache.items

        if start is not None:
            items = [
                item
                for item in items
                if item.date >= start
            ]

        if end is not None:
            items = [
                item
                for item in items
                if item.date <= end
            ]

        return FundHistoryCache(
            update_date=cache.update_date,
            fund_code=cache.fund_code,
            items=items,
        )

    # =========================
    # 快捷查询接口
    # =========================

    def get_today_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        today = date.today()

        return self.get_history(
            fund_code,
            start=today,
            end=today,
        )

    def get_yesterday_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        yesterday = date.today() - timedelta(days=1)

        return self.get_history(
            fund_code,
            start=yesterday,
            end=yesterday,
        )

    def get_last_week_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=date.today() - timedelta(days=7),
        )

    def get_last_month_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_month(-1),
        )

    def get_last_3_months_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_month(-3),
        )

    def get_last_6_months_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_month(-6),
        )

    def get_last_year_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_year(-1),
        )

    def get_last_3_years_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_year(-3),
        )

    def get_last_5_years_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_year(-5),
        )

    def get_last_10_years_history(
            self,
            fund_code: str,
    ) -> FundHistoryCache:
        return self.get_history(
            fund_code,
            start=self._shift_year(-10),
        )

    # =========================
    # 更新接口
    # =========================

    # def update(
    #         self,
    #         fund_code: str,
    #         force: bool = False,
    # ):
    #     """
    #     更新单个基金历史数据
    #
    #     Args:
    #         fund_code:
    #             基金代码
    #
    #         force:
    #             是否强制重新下载
    #     """
    #
    #     cache = self._load_cache(fund_code)
    #
    #     if not force and not self._need_update(cache):
    #         return
    #
    #     items = self._download(fund_code)
    #
    #     if not items:
    #         return
    #
    #     cache = FundHistoryCache(
    #         update_date=items[-1].date,
    #         fund_code=fund_code,
    #         items=items,
    #     )
    #
    #     self._save_cache(cache)

    def update_all(
            self,
            force: bool = False,
    ):
        """
        更新全部基金历史数据
        """

        funds: list[FundData] = (
            FundInfoRepository().get_all()
        )

        for fund in funds:
            self.update(
                fund.code,
                force=force,
            )

    # =========================
    # 日期工具
    # =========================

    @staticmethod
    def _shift_month(months: int) -> date:
        """
        月份偏移

        例如：
        当前日期 2026-07-31

        months=-3

        返回:
        2026-04-30
        """

        today = date.today()

        year = today.year
        month = today.month + months

        while month <= 0:
            year -= 1
            month += 12

        while month > 12:
            year += 1
            month -= 12

        day = min(
            today.day,
            28,
        )

        return date(
            year,
            month,
            day,
        )

    @staticmethod
    def _shift_year(years: int) -> date:
        today = date.today()

        return date(
            today.year + years,
            today.month,
            today.day,
        )

    # =========================
    # 数据下载
    # =========================

    def _download(
            self,
            fund_code: str,
    ):
        """
        从AKShare下载基金历史数据

        返回:
            list[FundHistoryItem]
        """

        unit_df = ak.fund_open_fund_info_em(
            symbol=fund_code,
            indicator="单位净值走势",
        )

        if unit_df.empty:
            return []

        accumulated_df = ak.fund_open_fund_info_em(
            symbol=fund_code,
            indicator="累计净值走势",
        )

        return self._parse(
            unit_df,
            accumulated_df,
        )

    def _parse(
            self,
            unit_df,
            accumulated_df,
    ):
        """
        将AKShare DataFrame转换为FundHistoryItem
        """

        from src.funds.fund_data import FundHistoryItem

        if unit_df.empty:
            return []

        # 合并累计净值
        df = unit_df.merge(
            accumulated_df,
            on="净值日期",
            how="left",
        )

        df = df.sort_values(
            "净值日期"
        )

        items = []

        for _, row in df.iterrows():

            daily_change = row["日增长率"]

            if daily_change != daily_change:
                # NaN
                daily_change = 0.0
            else:
                # AKShare返回:
                # 1.25 表示 1.25%
                #
                # 内部统一:
                # 0.0125
                daily_change = (
                        float(daily_change) / 100
                )

            item = FundHistoryItem(
                date=row["净值日期"],
                unit_nav=float(
                    row["单位净值"]
                ),
                accumulated_nav=float(
                    row["累计净值"]
                ),
                daily_change=daily_change,
            )

            items.append(item)

        return items

    # =========================
    # 缓存
    # =========================

    def _load_cache(
            self,
            fund_code: str,
    ) -> FundHistoryCache | None:
        """
        加载缓存
        """

        path = self._get_cache_path(
            fund_code
        )

        if not path.exists():
            return None

        with path.open(
                "rb"
        ) as f:
            return pickle.load(f)

    def _save_cache(
            self,
            cache: FundHistoryCache,
    ):
        """
        保存缓存
        """

        path = self._get_cache_path(
            cache.fund_code
        )

        with path.open(
                "wb"
        ) as f:
            pickle.dump(
                cache,
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    def _get_cache_path(
            self,
            fund_code: str,
    ) -> Path:
        """
        获取缓存路径
        """

        return (
                self.history_dir
                / f"{fund_code}.pkl"
        )

    # =========================
    # 更新判断
    # =========================

    def _need_update(
            self,
            cache: FundHistoryCache | None,
    ) -> bool:
        """
        判断是否需要更新缓存

        注意:
        update_date表示最后有效净值日期
        """

        if cache is None:
            return True

        if not cache.items:
            return True

        latest_date = cache.update_date

        now = datetime.now()

        today = now.date()

        yesterday = (
                today - timedelta(days=1)
        )

        # 15点以前
        if now.hour < 15:

            # 昨天的数据已经存在
            if latest_date >= yesterday:
                return False

            return True

        # 15点以后
        else:

            # 今天的数据已经存在
            if latest_date >= today:
                return False

            # 可能基金还没有更新
            # 尝试更新
            return True

    def _ensure_updated(
            self,
            fund_code: str,
    ):
        """
        查询前确保缓存可用
        """

        cache = self._load_cache(
            fund_code
        )

        if self._need_update(cache):
            self.update(
                fund_code
            )

    # =========================
    # 初始化检查缓存
    # =========================

    def _init_runtime_cache(self):
        """
        初始化运行时缓存

        用于避免一天内重复检查同一个基金
        """

        if not hasattr(
                self,
                "_checked_funds",
        ):
            self._checked_funds = set()

    def _already_checked_today(
            self,
            fund_code: str,
    ) -> bool:
        """
        判断当前运行周期内是否已经检查过
        """

        self._init_runtime_cache()

        return fund_code in self._checked_funds

    def _mark_checked(
            self,
            fund_code: str,
    ):
        """
        标记已经检查
        """

        self._init_runtime_cache()

        self._checked_funds.add(
            fund_code
        )

    # =========================
    # 覆盖 update
    # =========================

    def update(
            self,
            fund_code: str,
            force: bool = False,
    ):
        """
        更新单个基金历史数据

        force=True:
            强制重新下载
        """

        cache = self._load_cache(
            fund_code
        )

        if (
                not force
                and not self._need_update(cache)
        ):
            return

        # 标记已经尝试更新
        self._mark_checked(
            fund_code
        )

        items = self._download(
            fund_code
        )

        if not items:
            return

        new_cache = FundHistoryCache(
            update_date=items[-1].date,
            fund_code=fund_code,
            items=items,
        )

        self._save_cache(
            new_cache
        )

    # =========================
    # 缓存管理
    # =========================

    def clear(
            self,
            fund_code: str,
    ):
        """
        删除指定基金缓存
        """

        path = self._get_cache_path(
            fund_code
        )

        if path.exists():
            path.unlink()

    def clear_all(self):
        """
        清空全部基金历史缓存
        """

        for path in self.history_dir.glob(
                "*.pkl"
        ):
            path.unlink()

    # =========================
    # 缓存信息
    # =========================

    def cache_exists(
            self,
            fund_code: str,
    ) -> bool:
        """
        判断基金是否存在缓存
        """

        return self._get_cache_path(
            fund_code
        ).exists()

    def get_cache_info(
            self,
            fund_code: str,
    ) -> FundHistoryCache | None:
        """
        获取缓存信息

        不触发更新
        """

        return self._load_cache(
            fund_code
        )


def print_history(title, history, limit=5):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    print(f"基金代码: {history.fund_code}")
    print(f"缓存日期: {history.update_date}")
    print(f"数据数量: {len(history.items)}")

    print("\n前几条:")

    for item in history.items[:limit]:
        print(
            item.date,
            item.unit_nav,
            item.accumulated_nav,
            item.daily_change,
        )

    if len(history.items) > limit:
        print("...")

        print("\n最后一条:")

        item = history.items[-1]

        print(
            item.date,
            item.unit_nav,
            item.accumulated_nav,
            item.daily_change,
        )


def main():
    # ======================
    # 初始化
    # ======================

    repo = FundHistoryRepository()

    # 测试基金
    # 沪深300ETF联接A
    fund_code = "000051"

    # ======================
    # 1. 查询全部历史
    # ======================

    history = repo.get_history(
        fund_code
    )

    print_history(
        "1. 全部历史",
        history,
    )

    # ======================
    # 2. 自定义日期查询
    # ======================

    history = repo.get_history(
        fund_code,
        start=date(2023, 1, 1),
        end=date(2023, 6, 1),
    )

    print_history(
        "2. 2023-01-01 到 2023-06-01",
        history,
    )

    # ======================
    # 3. 只指定开始日期
    # ======================

    history = repo.get_history(
        fund_code,
        start=date(2025, 1, 1),
    )

    print_history(
        "3. 从2025年至今",
        history,
    )

    # ======================
    # 4. 只指定结束日期
    # ======================

    history = repo.get_history(
        fund_code,
        end=date(2023, 12, 31),
    )

    print_history(
        "4. 起始到2023年底",
        history,
    )

    # ======================
    # 5. auto_update=False
    # ======================

    history = repo.get_history(
        fund_code,
        auto_update=False,
    )

    print_history(
        "5. 不自动更新缓存",
        history,
    )

    # ======================
    # 6. 快捷查询
    # ======================

    methods = [
        (
            "今日",
            repo.get_today_history,
        ),
        (
            "昨日",
            repo.get_yesterday_history,
        ),
        (
            "最近一周",
            repo.get_last_week_history,
        ),
        (
            "最近一月",
            repo.get_last_month_history,
        ),
        (
            "最近3个月",
            repo.get_last_3_months_history,
        ),
        (
            "最近6个月",
            repo.get_last_6_months_history,
        ),
        (
            "最近一年",
            repo.get_last_year_history,
        ),
        (
            "最近3年",
            repo.get_last_3_years_history,
        ),
        (
            "最近5年",
            repo.get_last_5_years_history,
        ),
        (
            "最近10年",
            repo.get_last_10_years_history,
        ),
    ]

    for name, func in methods:

        try:
            history = func(
                fund_code
            )

            print_history(
                f"6. {name}",
                history,
                limit=3,
            )

        except Exception as e:

            print(
                f"{name} 查询失败:",
                e,
            )

    # ======================
    # 7. 缓存信息
    # ======================

    cache = repo.get_cache_info(
        fund_code
    )

    print("\n缓存信息:")
    # print(cache)

    # ======================
    # 8. 判断缓存存在
    # ======================

    print(
        "\n缓存是否存在:",
        repo.cache_exists(
            fund_code
        ),
    )

    # ======================
    # 9. 强制更新
    # ======================

    print("\n开始强制更新:")

    repo.update(
        fund_code,
        force=True,
    )

    print("更新完成")

    # ======================
    # 10. 清理测试缓存
    # ======================

    # 注意：
    # 如果取消注释，会删除缓存
    #
    # repo.clear(fund_code)

    # ======================
    # 11. 全量更新
    # ======================

    # 不建议测试时打开
    #
    # repo.update_all(
    #     force=False
    # )


if __name__ == "__main__":
    main()
