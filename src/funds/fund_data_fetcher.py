import os
from pathlib import Path
import pandas as pd
import akshare as ak


class FundDataFetcher:
    """
    单只基金历史净值获取与本地缓存（增量更新）
    """

    BASE_DIR = Path("../../data/funds/history")

    def __init__(self, fund_code: str):
        if not fund_code.isdigit() or len(fund_code) != 6:
            raise ValueError("基金代码必须是 6 位数字")

        self.fund_code = fund_code
        self.file_path = self.BASE_DIR / f"{fund_code}.csv"
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> pd.DataFrame:
        """
        主入口：
        - 若本地数据已是最新 → 直接读取
        - 否则 → 增量更新
        """
        if not self.file_path.exists():
            df = self._fetch_full()
            df.to_csv(self.file_path, index=False)
            return df

        local_df = pd.read_csv(self.file_path, parse_dates=["日期"])
        last_date = local_df["日期"].max()

        new_df = self._fetch_since(last_date)

        if new_df.empty:
            return local_df

        merged = (
            pd.concat([local_df, new_df], ignore_index=True)
            .drop_duplicates(subset=["日期"], keep="last")
            .sort_values("日期")
        )

        merged.to_csv(self.file_path, index=False)
        return merged

    # ============================
    # 数据获取逻辑
    # ============================

    def _fetch_full(self) -> pd.DataFrame:
        """首次获取全量数据"""
        df = self._fetch_from_source()
        return df.sort_values("日期")

    def _fetch_since(self, last_date: pd.Timestamp) -> pd.DataFrame:
        """获取 last_date 之后的增量"""
        df = self._fetch_from_source()
        return df[df["日期"] > last_date]

    def _fetch_from_source(self) -> pd.DataFrame:
        """从 AKShare 拉取并整理字段"""

        # 单位净值 + 日涨跌幅
        nav_df = ak.fund_open_fund_info_em(
            symbol=self.fund_code,
            indicator="单位净值走势"
        )

        nav_df = nav_df.rename(columns={
            "净值日期": "日期",
            "单位净值": "单位净值",
            "日增长率": "日涨跌幅"
        })

        # 累积净值
        acc_df = ak.fund_open_fund_info_em(
            symbol=self.fund_code,
            indicator="累计净值走势"
        )

        acc_df = acc_df.rename(columns={
            "净值日期": "日期",
            "累计净值": "累积净值"
        })

        # 合并
        df = pd.merge(nav_df, acc_df, on="日期", how="left")

        df["日期"] = pd.to_datetime(df["日期"])
        df = df[["日期", "单位净值", "累积净值", "日涨跌幅"]]

        return df


def update_fund_files(codes: list[str], verbose: bool = True) -> None:
    """
    对传入的基金代码列表逐只进行“增量更新并保存到 CSV”。
    - 不返回任何值，仅在控制台打印结果（或根据 verbose 控制）
    - CSV 路径： ../../data/funds/history/{code}.csv
    """
    for code in codes:
        try:
            fetcher = FundDataFetcher(code)
            df = fetcher.load()
            if verbose:
                print(f"[OK] 基金 {code} 更新完成，数据行数：{len(df)}，最近日期：{df['日期'].max().date()}")
        except Exception as e:
            # 打印简洁错误信息，便于定位
            print(f"[ERROR] 基金 {code} 更新失败：{e}")


if __name__ == "__main__":
    # 更新CSV
    FUND_CODES = ["018125", "025209"]
    update_fund_files(FUND_CODES)
