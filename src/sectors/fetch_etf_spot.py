"""
关注 ETF 每日数据抓取与归档。

数据源:
- ak.fund_etf_hist_em  单只 ETF 历史行情(含每日涨跌幅)，用于补历史数据
- ak.fund_etf_spot_em  全市场 ETF 实时快照，用于当日兜底

归档:
- data/sectors/etf/YYYY-MM/YYYY-MM-DD.csv      关注 ETF 当日行情
- data/sectors/sectors/YYYY-MM/YYYY-MM-DD.csv  当日板块涨跌幅(由 sector_data 计算)

只保存"关注板块"映射表(sector_etf_map.yaml)中出现的 ETF，不保存全市场。

用法:
    from src.sectors.fetch_etf_spot import ETFDataFetcher
    fetcher = ETFDataFetcher()
    fetcher.fetch_and_archive_today()   # 抓当日并归档
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

    def fetch_archive_today(self) -> tuple[Path | None, Path | None]:
        """
        抓取当日关注 ETF 数据并归档。
        返回 (etf_csv_path, sector_csv_path)，任一失败对应为 None。
        """
        # 优先 hist(单只逐只)，失败或部分失败时用 spot 兜底整日
        today = date.today()
        yyyymm = today.strftime("%Y-%m")
        yyyymmdd = today.strftime("%Y-%m-%d")

        etf_data = self.fetch_spot_today()
        if not etf_data:
            print("[ETFDataFetcher] 当日 ETF 数据抓取失败，跳过归档")
            return None, None

        # 写入 etf 归档
        etf_csv = self._write_etf_csv(etf_data, yyyymm, yyyymmdd)

        # 计算板块并归档
        sector_csv = self._write_sector_csv(yyyymm, yyyymmdd)
        return etf_csv, sector_csv

    def archive_history(self, start_date: str, end_date: str) -> dict[str, tuple[Path | None, Path | None]]:
        """
        拉取关注 ETF 在 [start_date, end_date] 窗口内的历史数据并逐日归档。
        start_date/end_date 格式 YYYYMMDD。
        返回 {YYYY-MM-DD: (etf_csv, sector_csv)}，某日无数据则对应为 None。
        """
        codes = self.watched_codes()
        print(f"[ETFDataFetcher] 开始拉取 {len(codes)} 只关注 ETF 历史数据 ({start_date} ~ {end_date})")

        # 按日期聚合: {trade_date: {code: ETFDayData}}
        by_date: dict[str, dict[str, ETFDayData]] = {}
        for idx, code in enumerate(codes, 1):
            rows = self.fetch_etf_history(code, start_date, end_date)
            for r in rows:
                by_date.setdefault(r.trade_date, {})[code] = r
            if idx % 10 == 0:
                print(f"[ETFDataFetcher] 已处理 {idx}/{len(codes)} 只...")

        print(f"[ETFDataFetcher] 共 {len(by_date)} 个交易日, 开始归档")
        result: dict[str, tuple[Path | None, Path | None]] = {}
        for d in sorted(by_date):
            yyyymm = d[:7]
            etf_csv = self._write_etf_csv(by_date[d], yyyymm, d)
            # 从该日归档的 ETF 数据计算板块(避免依赖默认 spot)
            sector_csv = self._write_sector_csv_from_dir(yyyymm, d)
            result[d] = (etf_csv, sector_csv)
        return result

    @staticmethod
    def _write_sector_csv_from_dir(yyyymm: str, yyyymmdd: str) -> Path | None:
        """从指定日期的 etf 归档数据计算板块并写 sectors/YYYY-MM/YYYY-MM-DD.csv。"""
        from src.sectors.sector_data import SectorRepository

        repo = SectorRepository()
        flatten = repo.get_flatten_sectors(trade_date=yyyymmdd)

        out_dir = SECTOR_ARCHIVE_DIR / yyyymm
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{yyyymmdd}.csv"

        rows = []
        for s in flatten:
            rows.append({
                "板块id": s.id,
                "板块名称": s.name,
                "涨跌幅": s.change_rate,
                "ETF数量": len(s.etfs),
            })
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[ETFDataFetcher] 已归档板块数据: {path} ({len(rows)}个板块)")
        return path

    # =========================
    # 归档
    # =========================

    @staticmethod
    def _write_etf_csv(data: dict[str, ETFDayData], yyyymm: str, yyyymmdd: str) -> Path | None:
        """写 etf/YYYY-MM/YYYY-MM-DD.csv。"""
        if not data:
            return None
        out_dir = ETF_ARCHIVE_DIR / yyyymm
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{yyyymmdd}.csv"

        rows = [d.to_row() for d in sorted(data.values(), key=lambda x: x.fund_code)]
        df = pd.DataFrame(rows)
        # 统一列顺序
        cols = ["代码", "名称", "日期", "开盘", "收盘", "最高", "最低",
                "成交量", "成交额", "涨跌额", "涨跌幅"]
        df = df[cols]
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[ETFDataFetcher] 已归档 ETF 数据: {path} ({len(rows)}只)")
        return path

    @staticmethod
    def _write_sector_csv(yyyymm: str, yyyymmdd: str) -> Path | None:
        """调用 sector_data 计算当日板块涨跌幅并写 sectors/YYYY-MM/YYYY-MM-DD.csv。"""
        from src.sectors.sector_data import SectorRepository

        repo = SectorRepository()
        flatten = repo.get_flatten_sectors()

        out_dir = SECTOR_ARCHIVE_DIR / yyyymm
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{yyyymmdd}.csv"

        rows = []
        for s in flatten:
            rows.append({
                "板块id": s.id,
                "板块名称": s.name,
                "涨跌幅": s.change_rate,
                "ETF数量": len(s.etfs),
            })
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[ETFDataFetcher] 已归档板块数据: {path} ({len(rows)}个板块)")
        return path

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
