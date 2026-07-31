from __future__ import annotations
import pickle
from datetime import date
import akshare as ak

from src.config.path import FUNDS_DIR, FUND_LIST_CACHE_PATH
from src.funds.fund_data import FundData, FundListCache


class FundInfoRepository:
    CACHE_FILE = FUND_LIST_CACHE_PATH

    def __init__(self):
        self._funds_by_code: dict[str, FundData] = {}
        self._funds_by_name: dict[str, FundData] = {}
        self._fund_list: list[FundData] = []

        self._cache: FundListCache | None = None

        self._ensure_cache()
        self._load_cache()

    # =======================================================
    # public
    # =======================================================

    def get_by_code(self, code: str) -> FundData | None:
        """
        根据基金代码查询基金。

        Parameters
        ----------
        code
            基金代码

        Returns
        -------
        FundData | None
            查询成功返回 FundData，否则返回 None。
        """
        return self._funds_by_code.get(code.strip())

    def get_by_name(self, name: str) -> FundData | None:
        """
        根据基金名称查询基金。

        Parameters
        ----------
        name
            基金名称

        Returns
        -------
        FundData | None
            查询成功返回 FundData，否则返回 None。
        """
        return self._funds_by_name.get(self._normalize_name(name))

    def code_to_name(self, code: str) -> str | None:
        fund = self.get_by_code(code)
        return None if fund is None else fund.name

    def name_to_code(self, name: str) -> str | None:
        fund = self.get_by_name(name)
        return None if fund is None else fund.code

    def search(self, keyword: str, limit: int | None = 20) -> list[FundData]:
        """
        根据基金名称或代码进行模糊搜索。

        Parameters
        ----------
        keyword
            搜索关键词，可为基金名称的一部分或基金代码。

        limit
            返回结果数量限制。
            None 表示返回全部结果。

        Returns
        -------
        list[FundData]
        """
        keyword = self._normalize_name(keyword)
        result = [
            fund for fund in self._funds_by_code.values()
            if keyword in self._normalize_name(fund.name) or keyword in fund.code
        ]
        result.sort(key=lambda x: (keyword not in self._normalize_name(x.name), len(x.name)))

        if limit is not None:
            result = result[:limit]

        return result

    # 修改
    def refresh(self):
        """
        强制刷新基金列表。
        若 AkShare 获取失败，则继续使用旧缓存。
        """
        try:
            funds = self._fetch_from_akshare()
        except Exception as e:
            print(f"[FundRepository] 更新基金列表失败：{e}")
            # 已有缓存，则继续使用旧缓存
            if self._cache is not None:
                return
            # 初始化时没有缓存，则无法继续
            raise
        self._cache = FundListCache(
            update_date=date.today(),
            funds=funds,
        )
        assert self._cache is not None
        self._save_cache()
        self._build_index(funds)
        print("[FundInfoRepository-refresh] 刷新成功")

    def get_all(self) -> list[FundData]:
        """
        获取全部基金。

        Returns
        -------
        list[FundData]
            按基金代码升序排列的基金列表。
        """
        # 返回副本，防止调用者修改内部数据
        return self._fund_list.copy()
    # =======================================================
    # cache
    # =======================================================

    def _ensure_cache(self):
        """确保基金缓存存在且为今日数据"""
        # 缓存不存在，首次下载
        if not self.CACHE_FILE.exists():
            self.refresh()
            return
        try:
            with self.CACHE_FILE.open("rb") as f:
                cache: FundListCache = pickle.load(f)
            # 不是今天的数据，尝试更新
            if cache.update_date != date.today():
                self.refresh()
        except Exception:
            self.refresh()

    def _load_cache(self):
        if not self.CACHE_FILE.exists():
            raise FileNotFoundError(
                f"基金缓存不存在：{self.CACHE_FILE}"
            )
        with self.CACHE_FILE.open("rb") as f:
            self._cache = pickle.load(f)
        assert self._cache is not None
        self._build_index(self._cache.funds)

    def _save_cache(self):
        self.CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        with self.CACHE_FILE.open("wb") as f:
            pickle.dump(self._cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    # =======================================================
    # fetch
    # =======================================================

    @staticmethod
    def _fetch_from_akshare() -> list[FundData]:
        """
        从 AkShare 获取全部基金列表。

        Returns
        -------
        list[FundData]
        """
        df = ak.fund_name_em()
        return [
            FundData(
                code=str(row["基金代码"]).strip(),
                name=str(row["基金简称"]).strip(),
            )
            for _, row in df.iterrows()
        ]

    # =======================================================
    # index
    # =======================================================

    def _build_index(self, funds: list[FundData]):
        self._funds_by_code.clear()
        self._funds_by_name.clear()
        self._fund_list = sorted(funds, key=lambda fund: fund.code)  # 按基金代码升序排列
        for fund in funds:
            self._funds_by_code[fund.code] = fund
            self._funds_by_name[self._normalize_name(fund.name)] = fund

    # =======================================================
    # utils
    # =======================================================

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.replace(" ", "").replace("　", "").strip().lower()

    def __getitem__(self, item: str) -> FundData:
        fund = self.get_by_code(item)
        if fund is None:
            fund = self.get_by_name(item)
        if fund is None:
            raise KeyError(item)
        return fund

    def __contains__(self, item: str):
        return item in self._funds_by_code or self._normalize_name(item) in self._funds_by_name

    def __len__(self):
        return len(self._funds_by_code)

    def __iter__(self):
        """遍历全部基金（按基金代码升序）"""
        return iter(self._fund_list)

    @property
    def update_date(self) -> date:
        """基金列表更新时间"""
        return self._cache.update_date


if __name__ == "__main__":
    repo = FundInfoRepository()
    fund = repo.get_by_code("025209")  # 根据代码查询
    print(fund)
    fund = repo.get_by_name("永赢先锋半导体智选混合发起C")  # 根据名称查询
    print(fund.code)
    print(repo.name_to_code("永赢先锋半导体智选混合发起C"))  # 名称转代码
    print(repo.code_to_name("025209"))  # 代码转名称
    # 支持[]
    print(repo["025209"])
    print(repo["永赢先锋半导体智选混合发起C"])
    if "025209" in repo:
        print("存在")
    if "永赢先锋半导体智选混合发起C" in repo:
        print("存在")
    print(f"基金数量：{len(repo)}")
    for fund in repo.search("永赢", limit=5):
        print(fund.code, fund.name)
