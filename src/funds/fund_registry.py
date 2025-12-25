"""
funds_catalog.py
将基金代码/简称获取与查询封装为类
依赖: akshare, pandas
"""

from __future__ import annotations
import os
from typing import List, Optional, Tuple
import pandas as pd
import akshare as ak

DEFAULT_CSV = "../../data/funds/funds_code.csv"


class FundsCatalog:
    """
    管理基金代码 <-> 基金简称 映射的类。
    - 初始化会载入本地 CSV（若不存在则自动从网络抓取并保存）。
    - 后续查询基于内存中的 DataFrame，不会重复读取文件或网络，除非调用 refresh()。
    """

    def __init__(self, csv_path: str = DEFAULT_CSV, auto_fetch: bool = True) -> None:
        self.csv_path = csv_path
        self._df: Optional[pd.DataFrame] = None
        # 当 auto_fetch=True 时，立即加载（若文件不存在则抓取）
        if auto_fetch:
            self.load()

    # -------------------------
    # I/O 与加载
    # -------------------------
    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)

    def fetch_from_network(self) -> pd.DataFrame:
        """
        使用 akshare 从网络抓取基金表并返回 DataFrame（未保存到盘）。
        """
        df = ak.fund_name_em()
        # 兼容不同版本的列名
        df = self._normalize_columns(df)
        # 代码确保为6位字符串
        df["基金代码"] = df["基金代码"].astype(str).str.zfill(6)
        return df

    def save(self, path: Optional[str] = None) -> None:
        """
        将当前内存中的 DataFrame 保存为 CSV（utf-8-sig）。
        """
        if self._df is None:
            raise RuntimeError("没有可保存的数据。请先调用 load() 或 fetch_from_network().")
        target = path or self.csv_path
        os.makedirs(os.path.dirname(target), exist_ok=True)
        self._df.to_csv(target, index=False, encoding="utf-8-sig")

    def load(self, path: Optional[str] = None) -> pd.DataFrame:
        """
        从本地 CSV 加载 DataFrame；如果文件不存在则从网络抓取并保存后加载。
        返回加载的 DataFrame。
        """
        target = path or self.csv_path
        if not os.path.exists(target):
            # 自动抓取并保存
            df = self.fetch_from_network()
            os.makedirs(os.path.dirname(target), exist_ok=True)
            df.to_csv(target, index=False, encoding="utf-8-sig")
            self._df = df
            return self._df
        # 从本地加载
        df = pd.read_csv(target, dtype=str)
        # 兼容列名
        df = self._normalize_columns(df)
        if "基金代码" not in df.columns or "基金简称" not in df.columns:
            raise RuntimeError("本地 CSV 未包含 '基金代码' 或 '基金简称' 列。")
        df["基金代码"] = df["基金代码"].astype(str).str.zfill(6)
        self._df = df
        return self._df

    def refresh(self, save: bool = True) -> pd.DataFrame:
        """
        强制从网络刷新数据。fetch -> 保存（可选） -> 更新内存 DataFrame。
        """
        df = self.fetch_from_network()
        self._df = df
        if save:
            self.save()
        return self._df

    # -------------------------
    # 依据基金代码查名称
    # -------------------------
    def code_to_name(self, code: str) -> Optional[str]:
        """
        通过基金代码（可以包含后缀或不是严格6位）查找基金简称。
        返回第一个匹配到的基金简称；未找到返回 None。
        """
        df = self._ensure_df_loaded()
        code = str(code).strip()
        digits = "".join(ch for ch in code if ch.isdigit())
        if len(digits) >= 6:
            code6 = digits[-6:]
        else:
            code6 = digits
        res = df.loc[df["基金代码"] == code6]
        if not res.empty:
            return res.iloc[0]["基金简称"]
        return None

    # -------------------------
    # 依据基金简称查代码
    # -------------------------
    def name_to_code(self, name: str, fuzzy: bool = True) -> List[Tuple[str, str]]:
        """
        通过基金简称查代码。
        - fuzzy=True: 先精确匹配，再做包含匹配；返回匹配对列表 [(code, name), ...]
        - fuzzy=False: 仅精确匹配
        """
        df = self._ensure_df_loaded()
        name = str(name).strip()
        # 精确匹配
        exact = df.loc[df["基金简称"] == name]
        if not exact.empty:
            return list(exact[["基金代码", "基金简称"]].itertuples(index=False, name=None))
        if fuzzy:
            contains = df.loc[df["基金简称"].str.contains(name, na=False)]
            return list(contains[["基金代码", "基金简称"]].itertuples(index=False, name=None))
        return []

    def search_by_keyword(self, keyword: str, limit: int = 50) -> List[Tuple[str, str]]:
        """
        更通用的模糊搜索（包含匹配），按出现顺序返回前 limit 条 (code, name)。
        """
        df = self._ensure_df_loaded()
        kw = str(keyword).strip()
        matches = df.loc[df["基金简称"].str.contains(kw, na=False)]
        pairs = list(matches[["基金代码", "基金简称"]].itertuples(index=False, name=None))
        return pairs[:limit]

    # -------------------------
    # 辅助/内部方法
    # -------------------------
    def _ensure_df_loaded(self) -> pd.DataFrame:
        if self._df is None:
            return self.load()
        return self._df

    # -------------------------
    # 列名兼容性处理
    # -------------------------
    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        兼容不同数据源/akshare 版本的列名，将常见候选列名映射到标准列名:
          - '基金代码' <- ('基金代码', '代码', 'fund_code', '基金编码', ...)
          - '基金简称' <- ('基金简称', '简称', 'name', 'fund_name', ...)
        如果已经包含标准列名则不变。
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError("_normalize_columns expects a pandas DataFrame")
        col_map = {}
        cols_lower = {c.lower(): c for c in df.columns}
        # 找 '基金代码'
        if "基金代码" not in df.columns:
            for key in ("基金代码", "代码", "fund_code", "基金编码"):
                if key.lower() in cols_lower:
                    col_map[cols_lower[key.lower()]] = "基金代码"
                    break
        # 找 '基金简称'
        if "基金简称" not in df.columns:
            for key in ("基金简称", "简称", "name", "fund_name"):
                if key.lower() in cols_lower:
                    col_map[cols_lower[key.lower()]] = "基金简称"
                    break
        if col_map:
            df = df.rename(columns=col_map)
        return df

    # -------------------------
    # 访问 self._df
    # -------------------------
    def get_df(self) -> pd.DataFrame:
        """返回内存中的 DataFrame（只读视图），便于外部进一步分析。"""
        return self._ensure_df_loaded().copy()


if __name__ == "__main__":
    catalog = FundsCatalog()  # 默认会 load()（若没有文件则会 fetch 并保存）
    # 单次查询不会再次从磁盘或网络读取
    print("示例：代码 -> 名称:", catalog.code_to_name("000001"))
    print("示例：名称 -> 代码:", catalog.name_to_code("华夏成长混合")[:10])
    print(catalog.name_to_code("永赢先锋")[:10])
    # 强制刷新网络数据并保存
    # catalog.refresh()
