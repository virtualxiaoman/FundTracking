"""
全基金历史净值排名索引。

职责:
- 扫描 data/funds/history 下全部基金历史缓存
- 为每个时间范围(range)预计算区间首尾净值与涨跌幅
- 结果落盘到 data/ranking/，过期自动重建

说明:
- 完全独立于 src/funds、src/config、src/portfolio 已有代码
- range 的计算直接复用 FundHistoryRepository 提供的快捷接口
- 只统计"首条与末条都在查询窗口内"的基金，窗口外的基金(如今年发售的
  基金查询近3年)不进入该 range 的排名；无净值数据的同样不显示
"""

from __future__ import annotations

import json
import pickle
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from src.config.path import DATA_DIR
from src.funds.fund_data import FundHistoryCache
from src.funds.fund_history import FundHistoryRepository

RANKING_DIR = DATA_DIR / "ranking"
RANKING_CACHE_PATH = RANKING_DIR / "ranking.json"

# 支持的查询范围及其对应 FundHistoryRepository 快捷接口
RANGE_MAP: dict[str, Callable[[str], FundHistoryCache]] = {
    "TODAY": FundHistoryRepository.get_today_history,
    "1W": FundHistoryRepository.get_last_week_history,
    "1M": FundHistoryRepository.get_last_month_history,
    "3M": FundHistoryRepository.get_last_3_months_history,
    "1Y": FundHistoryRepository.get_last_year_history,
    "3Y": FundHistoryRepository.get_last_3_years_history,
    "5Y": FundHistoryRepository.get_last_5_years_history,
    "ALL": None,  # 全部历史
}

# 索引有效期(秒)。扫描全部缓存较慢，落盘后短时间内直接复用。
INDEX_TTL_SECONDS = 12 * 3600


class FundRankingRepository:
    """
    全基金排名仓库。
    首次查询触发全量扫描并落盘，此后在 TTL 内直接读磁盘结果。
    """

    def __init__(self, history: FundHistoryRepository, path: Path = RANKING_CACHE_PATH,
                 ttl_seconds: int = INDEX_TTL_SECONDS):
        self._history = history
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._index: dict[str, list[dict]] | None = None  # range -> [{fund_code, ...}]
        self._built_at: datetime | None = None

    # =========================
    # 公共接口
    # =========================

    def get_ranking(self, range_key: str, sort: str = "desc", limit: int | None = None) -> list[dict]:
        """
        获取指定范围的基金涨跌幅排名。

        Args:
            range_key: RANGE_MAP 的 key (TODAY/1W/1M/3M/1Y/3Y/5Y/ALL)
            sort: desc=涨幅从高到低, asc=跌幅从高到低
            limit: 返回条数限制, None 返回全部

        Returns:
            [{fund_code, fund_name, first_date, last_date, first_nav,
              last_nav, change_rate}, ...] 已按涨跌幅排序
        """
        if range_key not in RANGE_MAP:
            raise ValueError(f"unknown range: {range_key}")

        with self._lock:
            self._ensure_index()
            rows = list(self._index.get(range_key, []))

        if sort == "asc":
            rows.sort(key=lambda r: r["change_rate"])
        else:
            rows.sort(key=lambda r: r["change_rate"], reverse=True)

        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows

    @property
    def ranges(self) -> list[str]:
        return list(RANGE_MAP.keys())

    # =========================
    # 索引构建
    # =========================

    def _ensure_index(self):
        """索引有效则直接使用，否则重建。"""
        if self._index is not None and self._built_at is not None:
            if datetime.now() - self._built_at < timedelta(seconds=self._ttl):
                return
        if self._load_from_disk():
            return
        self._build_and_save()

    def _load_from_disk(self) -> bool:
        """磁盘缓存未过期则加载。返回是否成功加载。"""
        if not self._path.exists():
            return False
        try:
            with self._path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            built_at = datetime.fromisoformat(raw["built_at"])
            if datetime.now() - built_at >= timedelta(seconds=self._ttl):
                return False
            self._index = raw["index"]
            self._built_at = built_at
            age = (datetime.now() - built_at).total_seconds()
            print(f"[FundRankingRepository] 从磁盘加载排名索引: {age:.0f}s 前构建")
            return True
        except Exception as e:
            print(f"[FundRankingRepository] 加载磁盘索引失败: {e}")
            return False

    def _build_and_save(self):
        """扫描全部基金缓存，构建索引并落盘。"""
        print("[FundRankingRepository] 开始扫描全部基金历史缓存...")
        index: dict[str, list[dict]] = {k: [] for k in RANGE_MAP}
        count = 0

        for cache in self._iter_all_caches():
            code = cache.fund_code
            for range_key in RANGE_MAP:
                change = self._compute_change(cache, range_key)
                if change is None:
                    continue
                index[range_key].append({
                    "fund_code": code,
                    "first_date": change["first_date"],
                    "last_date": change["last_date"],
                    "first_nav": change["first_nav"],
                    "last_nav": change["last_nav"],
                    "change_rate": change["change_rate"],  # 小数，如 0.0125 表示 +1.25%
                })
            count += 1
            if count % 5000 == 0:
                print(f"[FundRankingRepository] 已扫描 {count} 只...")

        self._index = index
        self._built_at = datetime.now()
        self._save()
        total = {k: len(v) for k, v in index.items()}
        print(f"[FundRankingRepository] 索引构建完成: 共 {count} 只, 各范围数量 {total}")

    def _iter_all_caches(self) -> list[FundHistoryCache]:
        """遍历全部基金历史缓存（只读文件，不触发更新）。"""
        files = sorted(self._history.history_dir.glob("*.pkl"))
        caches: list[FundHistoryCache] = []
        for path in files:
            try:
                with path.open("rb") as f:
                    import pickle
                    cache: FundHistoryCache = pickle.load(f)
                if cache.items:
                    caches.append(cache)
            except Exception:
                continue
        return caches

    @staticmethod
    def _compute_change(cache: FundHistoryCache, range_key: str) -> dict | None:
        """
        计算某基金在指定范围内的首末净值涨跌幅。
        首条与末条都必须落在窗口内，否则返回 None（窗口外不显示）。
        """
        items = cache.items
        if not items:
            return None

        start_date = _range_start_date(range_key)
        if start_date is not None:
            # 取窗口内数据；若窗口内无任何数据则不在该范围展示
            window = [it for it in items if it.date >= start_date]
            if not window:
                return None
        else:
            window = items

        first, last = window[0], window[-1]
        return {
            "first_date": first.date.isoformat(),
            "last_date": last.date.isoformat(),
            "first_nav": first.unit_nav,
            "last_nav": last.unit_nav,
            "change_rate": _nav_change(first.unit_nav, last.unit_nav),
        }

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "built_at": self._built_at.isoformat(),
            "index": self._index,
        }
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        tmp.replace(self._path)


def _nav_change(first_nav: float, last_nav: float) -> float:
    """计算涨跌幅（小数），净值非法或首净值为 0 时返回 0。"""
    if first_nav is None or last_nav is None or first_nav <= 0:
        return 0.0
    return last_nav / first_nav - 1.0


def _range_start_date(range_key: str) -> date | None:
    """返回各 range 的窗口起点日期；ALL 返回 None。"""
    today = date.today()
    if range_key == "TODAY":
        return today
    if range_key == "1W":
        return today - timedelta(days=7)
    if range_key == "1M":
        return _shift_month(-1)
    if range_key == "3M":
        return _shift_month(-3)
    if range_key == "1Y":
        return _shift_year(-1)
    if range_key == "3Y":
        return _shift_year(-3)
    if range_key == "5Y":
        return _shift_year(-5)
    return None


def _shift_month(months: int) -> date:
    today = date.today()
    year, month = today.year, today.month + months
    while month <= 0:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return date(year, month, min(today.day, 28))


def _shift_year(years: int) -> date:
    today = date.today()
    return date(today.year + years, today.month, today.day)


if __name__ == "__main__":
    repo = FundRankingRepository(FundHistoryRepository(), ttl_seconds=1)
    for rng in repo.ranges:
        rows = repo.get_ranking(rng, sort="desc", limit=3)
        print(f"\n[{rng}] 涨幅 TOP3:")
        for r in rows:
            print(f"  {r['fund_code']} {r['change_rate']*100:+.2f}%")
        rows = repo.get_ranking(rng, sort="asc", limit=3)
        print(f"[{rng}] 跌幅 TOP3:")
        for r in rows:
            print(f"  {r['fund_code']} {r['change_rate']*100:+.2f}%")
