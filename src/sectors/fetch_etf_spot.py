"""
关注 ETF 每日数据抓取与归档。

数据源:
- ak.fund_etf_hist_em  单只 ETF 历史行情(含每日涨跌幅)，用于补历史数据
- ak.fund_etf_spot_em  全市场 ETF 实时快照，用于当日兜底

归档(每只 ETF / 每个板块一个文件, 每行一个交易日, 日期升序):
- data/sectors/etf/{代码}.csv          单只关注 ETF 全部历史行情
- data/sectors/sectors/{板块id}.csv    单个板块历史涨跌幅

只保存"关注板块"映射表(sector_etf_map.yaml)中出现的 ETF，不保存全市场。

用法:
    from src.sectors.fetch_etf_spot import ETFDataFetcher
    fetcher = ETFDataFetcher()
    fetcher.fetch_archive_today()   # 抓当日并归档(追加到单文件)
    fetcher.archive_history(...)    # 补历史(追加到单文件)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import akshare as ak
import pandas as pd
import yaml

from src.config.path import SECTORS_DIR

ETF_MAP_PATH = Path(__file__).resolve().parent / "sector_etf_map.yaml"
ETF_ARCHIVE_DIR = SECTORS_DIR / "etf"
SECTOR_ARCHIVE_DIR = SECTORS_DIR / "sectors"

# ETF 单文件归档的列顺序
ETF_CSV_COLUMNS = ["日期", "名称", "开盘", "收盘", "最高", "最低",
                   "成交量", "成交额", "涨跌额", "涨跌幅"]
# 板块单文件归档的列顺序
SECTOR_CSV_COLUMNS = ["日期", "净值", "涨跌幅", "ETF数量"]


@dataclass(slots=True)
class ETFDayData:
    """单只 ETF 单日行情数据"""
    fund_code: str
    fund_name: str
    trade_date: str  # YYYY-MM-DD
    close: float | None          # 收盘价
    change_rate: float | None    # 涨跌幅，原始值(如 9.88 表示 +9.88%)
    change_amount: float | None  # 涨跌额
    open: float | None           # 开盘价
    high: float | None           # 最高价
    low: float | None            # 最低价
    volume: float | None         # 成交量
    turnover: float | None       # 成交额

    def to_row(self) -> dict:
        """转为 CSV 行。"""
        return {
            "代码": self.fund_code,
            "名称": self.fund_name,
            "日期": self.trade_date,
            "开盘": self.open,
            "收盘": self.close,
            "最高": self.high,
            "最低": self.low,
            "成交量": self.volume,
            "成交额": self.turnover,
            "涨跌额": self.change_amount,
            "涨跌幅": self.change_rate,
        }


class ETFDataFetcher:
    """ETF 数据抓取器：hist 优先，spot 兜底。"""

    def __init__(self, etf_map_path: Path = ETF_MAP_PATH):
        self.etf_map_path = etf_map_path
        self._watched_codes = self._load_watched_codes()

    # =========================
    # 公共接口
    # =========================

    def watched_codes(self) -> list[str]:
        """关注板块映射表中全部 ETF 代码(去重)。"""
        return list(self._watched_codes)

    def fetch_etf_history(self, fund_code: str, start_date: str, end_date: str) -> list[ETFDayData]:
        """
        抓取单只 ETF 历史行情。
        start_date/end_date 格式 YYYYMMDD。
        优先用东财 fund_etf_hist_em，失败降级用新浪 fund_etf_hist_sina(全量历史)。
        返回空列表表示全部失败。
        """
        rows = self._fetch_history_eastmoney(fund_code, start_date, end_date)
        if rows:
            return rows
        # 东财不可用时降级新浪
        rows = self._fetch_history_sina(fund_code, start_date, end_date)
        return rows

    def _fetch_history_eastmoney(self, fund_code: str, start_date: str, end_date: str) -> list[ETFDayData]:
        """东财 fund_etf_hist_em。"""
        try:
            df = ak.fund_etf_hist_em(
                symbol=fund_code, period="daily",
                start_date=start_date, end_date=end_date, adjust="",
            )
        except Exception as e:
            print(f"[ETFDataFetcher] 东财 hist 抓取失败 {fund_code}: {type(e).__name__} {e}")
            return []

        if df is None or df.empty:
            return []

        rows: list[ETFDayData] = []
        for _, rec in df.iterrows():
            rows.append(ETFDayData(
                fund_code=fund_code,
                fund_name=fund_code,
                trade_date=str(rec.get("日期", "")),
                close=_to_float(rec.get("收盘")),
                change_rate=_to_float(rec.get("涨跌幅")),
                change_amount=_to_float(rec.get("涨跌额")),
                open=_to_float(rec.get("开盘")),
                high=_to_float(rec.get("最高")),
                low=_to_float(rec.get("最低")),
                volume=_to_float(rec.get("成交量")),
                turnover=_to_float(rec.get("成交额")),
            ))
        return rows

    def _fetch_history_sina(self, fund_code: str, start_date: str, end_date: str) -> list[ETFDayData]:
        """
        新浪 fund_etf_hist_sina，返回全部历史日线，按日期窗口过滤。
        新浪返回无涨跌幅列，涨跌幅由收盘价环比计算。
        """
        symbol = self._sina_symbol(fund_code)
        if not symbol:
            return []
        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)
        except Exception as e:
            print(f"[ETFDataFetcher] 新浪 hist 抓取失败 {fund_code}: {type(e).__name__} {e}")
            return []

        if df is None or df.empty:
            return []

        start = _parse_yyyymmdd(start_date)
        end = _parse_yyyymmdd(end_date)

        rows: list[ETFDayData] = []
        prev_close: float | None = None
        for _, rec in df.iterrows():
            d = str(rec.get("date", ""))[:10]
            if start and d < start:
                prev_close = _to_float(rec.get("close"))  # 仍更新 prev_close 供环比
                continue
            if end and d > end:
                continue
            close = _to_float(rec.get("close"))
            change_rate = None
            if close is not None and prev_close is not None and prev_close > 0:
                change_rate = (close / prev_close - 1.0) * 100.0  # 转百分数，与东财涨跌幅一致
            rows.append(ETFDayData(
                fund_code=fund_code,
                fund_name=fund_code,
                trade_date=d,
                close=close,
                change_rate=change_rate,
                change_amount=None if close is None or prev_close is None else close - prev_close,
                open=_to_float(rec.get("open")),
                high=_to_float(rec.get("high")),
                low=_to_float(rec.get("low")),
                volume=_to_float(rec.get("volume")),
                turnover=_to_float(rec.get("amount")),
            ))
            prev_close = close
        return rows

    @staticmethod
    def _sina_symbol(fund_code: str) -> str:
        """
        ETF 代码转新浪格式。
        上海市场: 5/6 开头(sh)；深圳市场: 1/0 开头(sz)。
        """
        code = str(fund_code).strip()
        if not code:
            return ""
        if code.startswith(("5", "6")):
            return f"sh{code}"
        return f"sz{code}"

    def fetch_spot_today(self) -> dict[str, ETFDayData]:
        """
        用 fund_etf_spot_em 抓全市场快照，返回 {代码: ETFDayData}。
        只保留关注代码。数据日期取快照中的"数据日期"列。
        """
        try:
            df = ak.fund_etf_spot_em()
        except Exception as e:
            print(f"[ETFDataFetcher] spot 抓取失败: {type(e).__name__} {e}")
            return {}

        if df is None or df.empty:
            return {}

        trade_date = str(df.iloc[0].get("数据日期", date.today().isoformat()))[:10]
        result: dict[str, ETFDayData] = {}
        for _, rec in df.iterrows():
            code = str(rec.get("代码", "")).strip()
            if code not in self._watched_codes:
                continue
            result[code] = ETFDayData(
                fund_code=code,
                fund_name=str(rec.get("名称", code)),
                trade_date=trade_date,
                close=_to_float(rec.get("最新价")),
                change_rate=_to_float(rec.get("涨跌幅")),
                change_amount=_to_float(rec.get("涨跌额")),
                open=_to_float(rec.get("开盘价")),
                high=_to_float(rec.get("最高价")),
                low=_to_float(rec.get("最低价")),
                volume=_to_float(rec.get("成交量")),
                turnover=_to_float(rec.get("成交额")),
            )
        return result

    def fetch_archive_today(self) -> tuple[int, int]:
        """
        抓取当日关注 ETF 数据并归档到单文件(追加/合并)。
        返回 (更新的 ETF 数, 更新的板块数)。
        """
        etf_data = self.fetch_spot_today()
        if not etf_data:
            print("[ETFDataFetcher] 当日 ETF 数据抓取失败，跳过归档")
            return 0, 0

        n_etf = self._merge_etf_daily(etf_data)
        n_sector = self._update_sector_daily()
        return n_etf, n_sector

    def archive_history(self, start_date: str, end_date: str) -> dict[str, tuple[int, int]]:
        """
        拉取关注 ETF 在 [start_date, end_date] 窗口内的历史数据并合并进单文件归档。
        start_date/end_date 格式 YYYYMMDD。
        返回 {YYYY-MM-DD: (新增ETF数, 新增板块数)}，某日无数据则对应 (0,0)。
        """
        codes = self.watched_codes()
        print(f"[ETFDataFetcher] 开始拉取 {len(codes)} 只关注 ETF 历史数据 ({start_date} ~ {end_date})")

        # 每只 ETF 的历史行，直接合并进对应单文件
        total_new = 0
        for idx, code in enumerate(codes, 1):
            rows = self.fetch_etf_history(code, start_date, end_date)
            if rows:
                total_new += self._merge_etf_rows(rows)
            if idx % 10 == 0:
                print(f"[ETFDataFetcher] 已处理 {idx}/{len(codes)} 只...")

        # 重新计算各交易日板块并合并进板块单文件
        dates = self._available_dates()
        result: dict[str, tuple[int, int]] = {}
        n_sector_total = 0
        for d in sorted(dates):
            n = self._update_sector_daily_for_date(d)
            n_sector_total += n
            result[d] = (0, n)  # ETF 已实时合并，这里只报告板块更新
        print(f"[ETFDataFetcher] 归档完成: ETF 新增 {total_new} 行, 板块更新 {n_sector_total} 条")
        return result

    def archive_all_history(self) -> dict[str, tuple[int, int]]:
        """
        拉取全部关注 ETF 的全部历史数据并合并进单文件归档。
        东财 fund_etf_hist_em 优先；不可用时新浪 fund_etf_hist_sina 返回全量历史。
        等价于用极宽日期窗口调用 archive_history。
        """
        # 新浪返回全量历史，传足够宽的窗口即可覆盖到最早上市日
        start_date = "19900101"
        end_date = date.today().strftime("%Y%m%d")
        return self.archive_history(start_date, end_date)

    # =========================
    # 归档(单文件)
    # =========================

    def _merge_etf_daily(self, data: dict[str, ETFDayData]) -> int:
        """兼容旧调用: dict {代码: ETFDayData}。"""
        return self._merge_etf_rows(list(data.values()))

    def _merge_etf_rows(self, rows: list[ETFDayData]) -> int:
        """
        将多只 ETF 的单日(或多日)数据合并进 etf/{代码}.csv。
        按日期升序、去重(同日期覆盖)。
        返回实际写入的行数。
        """
        # 按代码分组
        by_code: dict[str, list[ETFDayData]] = {}
        for row in rows:
            by_code.setdefault(row.fund_code, []).append(row)

        written = 0
        for code, code_rows in by_code.items():
            path = ETF_ARCHIVE_DIR / f"{code}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)

            existing: pd.DataFrame
            if path.exists():
                existing = pd.read_csv(path, dtype={"日期": str})
            else:
                existing = pd.DataFrame(columns=ETF_CSV_COLUMNS)

            new_df = pd.DataFrame([r.to_row() for r in code_rows])
            # to_row 含 代码 列, 单文件内不需要
            if "代码" in new_df.columns:
                new_df = new_df.drop(columns=["代码"])

            merged = pd.concat([existing, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=["日期"], keep="last")
            merged = merged.sort_values("日期")
            # 统一列顺序
            merged = merged.reindex(columns=ETF_CSV_COLUMNS)
            merged.to_csv(path, index=False, encoding="utf-8-sig")
            written += len(code_rows)
        return written

    def _update_sector_daily(self) -> int:
        """用最新 spot 数据更新所有板块单文件(每个板块一行/日)。返回更新的板块数。"""
        repo = self._get_repo()
        flatten = repo.get_flatten_sectors()
        # 用最新交易日: 找第一个有 ETF 的板块的最近日期
        trade_date = ""
        for s in flatten:
            if s.etfs:
                trade_date = self._latest_etf_date(s.etfs[0].fund_code)
                break
        return self._write_sector_rows(flatten, trade_date)

    def _update_sector_daily_for_date(self, trade_date: str) -> int:
        """用指定日期的 etf 归档数据更新板块单文件。返回更新的板块数。"""
        repo = self._get_repo()
        flatten = repo.get_flatten_sectors(trade_date=trade_date)
        return self._write_sector_rows(flatten, trade_date)

    def _write_sector_rows(self, flatten, trade_date: str) -> int:
        """
        将某个交易日的板块涨跌幅合并进 sectors/{板块id}.csv。
        Args:
            flatten: 板块列表
            trade_date: 该日期的 YYYY-MM-DD
        返回更新的板块数。
        """
        n = 0
        for s in flatten:
            if s.change_rate is None:
                continue
            path = SECTOR_ARCHIVE_DIR / f"{s.id}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)

            row = {"日期": trade_date or "", "净值": s.nav, "涨跌幅": s.change_rate, "ETF数量": len(s.etfs)}

            existing: pd.DataFrame
            if path.exists():
                existing = pd.read_csv(path, dtype={"日期": str})
            else:
                existing = pd.DataFrame(columns=SECTOR_CSV_COLUMNS)

            new_df = pd.DataFrame([row])
            merged = pd.concat([existing, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=["日期"], keep="last")
            merged = merged.sort_values("日期")
            merged = merged.reindex(columns=SECTOR_CSV_COLUMNS)
            merged.to_csv(path, index=False, encoding="utf-8-sig")
            n += 1
        return n

    def _latest_etf_date(self, fund_code: str) -> str:
        """读取 etf/{code}.csv 的最后一行日期(最新交易日)。"""
        path = ETF_ARCHIVE_DIR / f"{fund_code}.csv"
        if not path.exists():
            return ""
        try:
            df = pd.read_csv(path, dtype={"日期": str})
            if df.empty:
                return ""
            return str(df["日期"].iloc[-1])
        except Exception:
            return ""

    def _available_dates(self) -> list[str]:
        """收集 etf 单文件里出现过的全部交易日(交集)。"""
        dates: set[str] = set()
        for path in ETF_ARCHIVE_DIR.glob("*.csv"):
            try:
                df = pd.read_csv(path, dtype={"日期": str})
                dates.update(str(d) for d in df["日期"] if pd.notna(d))
            except Exception:
                continue
        return sorted(dates)

    @staticmethod
    def _get_repo():
        from src.sectors.sector_data import SectorRepository
        return SectorRepository()

    # =========================
    # 内部
    # =========================

    def _load_watched_codes(self) -> set[str]:
        """从映射表读取全部关注 ETF 代码。"""
        with self.etf_map_path.open("r", encoding="utf-8") as f:
            etf_map = yaml.safe_load(f) or {}
        codes: set[str] = set()
        for main_cfg in etf_map.values():
            for child_cfg in main_cfg.values():
                if isinstance(child_cfg, list):
                    codes.update(str(c) for c in child_cfg)
        return codes


def _to_float(value) -> float | None:
    """安全转 float；空值/非法值返回 None。"""
    try:
        if value is None or pd.isna(value):
            return None
        f = float(value)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _parse_yyyymmdd(value: str) -> str:
    """YYYYMMDD 转 YYYY-MM-DD；非法返回空串。"""
    v = str(value).strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return ""


if __name__ == "__main__":
    fetcher = ETFDataFetcher()
    print("关注 ETF 数量:", len(fetcher.watched_codes()))
    etf_path, sector_path = fetcher.fetch_archive_today()
    print("ETF 归档:", etf_path)
    print("板块归档:", sector_path)
