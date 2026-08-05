"""
板块涨跌幅数据层。

数据来源:
- data/sectors/sector_tree.yaml      板块树(主板块 → 子板块)
- data/sectors/fund_etf_spot_em.csv  东方财富 ETF 实时快照
- src/sectors/sector_etf_map.yaml    板块 → ETF 代码映射表

功能:
- get_sector_tree()   返回带层级的主板块 → 子板块涨跌幅结构
- get_flatten_sectors() 返回平铺的所有子板块涨跌幅列表(内部复用 tree 逻辑)

约定:
- 板块涨跌幅 = 其绑定 ETF 涨跌幅(CSV 涨跌幅列)的均值
- 主板块涨跌幅 = 其子板块涨跌幅的均值(跳过无数据的子板块)
- 映射表为 null / ETF 在 CSV 中缺失时, 板块涨跌幅为 None
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.config.path import SECTORS_DIR

# ============================================================
# 数据模型
# ============================================================

@dataclass(slots=True)
class EtfInfo:
    """板块绑定的单只 ETF 信息"""
    fund_code: str
    fund_name: str
    change_rate: float | None  # 涨跌幅，原始值(如 0.125 表示 +12.5%)


@dataclass(slots=True)
class SectorData:
    """单个板块的涨跌幅数据"""
    id: str
    name: str
    change_rate: float | None  # 板块涨跌幅(小数)，无数据时为 None
    etfs: list[EtfInfo] = field(default_factory=list)  # 绑定的 ETF 明细


@dataclass(slots=True)
class MainSectorData:
    """主板块及其子板块"""
    id: str
    name: str
    change_rate: float | None  # 子板块均值，所有子板块无数据时为 None
    children: list[SectorData] = field(default_factory=list)


# ============================================================
# 数据加载
# ============================================================

class SectorRepository:
    """板块涨跌幅仓库。每次读取 CSV 快照计算，数据源本身为每日快照，无需缓存。"""

    def __init__(self, sectors_dir: Path = SECTORS_DIR):
        self.sector_tree_path = sectors_dir / "sector_tree.yaml"
        self.etf_csv_path = sectors_dir / "fund_etf_spot_em.csv"
        self.etf_map_path = Path(__file__).resolve().parent / "sector_etf_map.yaml"

    # =========================
    # 公共接口
    # =========================

    def get_sector_tree(self) -> list[MainSectorData]:
        """返回主板块 → 子板块的完整层级涨跌幅结构。"""
        tree = self._load_yaml(self.sector_tree_path)
        etf_rows = self._load_etf_rows()
        etf_map = self._load_yaml(self.etf_map_path)

        main_sectors = []
        for main_id, main_cfg in tree.items():
            children: list[SectorData] = []
            main_changes: list[float] = []
            # 该主板块下的子板块映射，如 {ai: [codes], semiconductor: [...]}
            main_map: dict = etf_map.get(main_id, {})

            for child_cfg in main_cfg["children"]:
                child = self._build_sector(child_cfg, main_map, etf_rows)
                children.append(child)
                if child.change_rate is not None:
                    main_changes.append(child.change_rate)

            main_sectors.append(MainSectorData(
                id=main_id,
                name=main_cfg["name"],
                change_rate=_mean(main_changes),
                children=children,
            ))

        return main_sectors

    def get_flatten_sectors(self) -> list[SectorData]:
        """返回平铺的所有子板块涨跌幅列表（不含主板块层级）。"""
        # 内部复用 get_sector_tree，从层级结果中摊平子板块
        flatten: list[SectorData] = []
        for main in self.get_sector_tree():
            flatten.extend(main.children)
        return flatten

    # =========================
    # 内部实现
    # =========================

    def _build_sector(self, child_cfg: dict, etf_map: dict, etf_rows: dict) -> SectorData:
        """根据子板块配置与映射表，构建子板块涨跌幅数据。"""
        sid = child_cfg["id"]
        name = child_cfg["name"]
        codes = etf_map.get(sid)

        if not codes:
            # 映射表为 null / 未配置
            return SectorData(id=sid, name=name, change_rate=None)

        etfs: list[EtfInfo] = []
        changes: list[float] = []
        for code in codes:
            row = etf_rows.get(code)
            if row is None:
                continue  # ETF 在 CSV 中缺失，跳过
            change = _csv_change_to_ratio(row.get("涨跌幅"))
            etfs.append(EtfInfo(
                fund_code=code,
                fund_name=row.get("名称", code),
                change_rate=change,
            ))
            if change is not None:
                changes.append(change)

        return SectorData(
            id=sid,
            name=name,
            change_rate=_mean(changes),
            etfs=etfs,
        )

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        """读取 yaml 文件为 dict。"""
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _load_etf_rows() -> dict[str, dict]:
        """读取 CSV 为 {代码: {列名: 值}} 映射。"""
        csv_path = SECTORS_DIR / "fund_etf_spot_em.csv"
        df = pd.read_csv(csv_path, dtype={"代码": str})
        df["代码"] = df["代码"].astype(str).str.strip()
        rows: dict[str, dict] = {}
        for record in df.to_dict(orient="records"):
            code = str(record.get("代码", "")).strip()
            if code:
                rows[code] = record
        return rows


def _mean(values: list[float]) -> float | None:
    """列表均值；空列表返回 None。"""
    if not values:
        return None
    return sum(values) / len(values)


def _csv_change_to_ratio(value: Any) -> float | None:
    """CSV 涨跌幅列(如 9.88 表示 +9.88%)转小数(0.0988)；非法值返回 None。"""
    try:
        if value is None or pd.isna(value):
            return None
        return float(value) / 100.0
    except (TypeError, ValueError):
        return None


def sector_data_to_dict(sector: SectorData) -> dict:
    """SectorData 转 dict（供 FastAPI 序列化）。"""
    return {
        "id": sector.id,
        "name": sector.name,
        "change_rate": sector.change_rate,
        "etfs": [
            {
                "fund_code": e.fund_code,
                "fund_name": e.fund_name,
                "change_rate": e.change_rate,
            }
            for e in sector.etfs
        ],
    }


def main_sector_to_dict(main: MainSectorData) -> dict:
    """MainSectorData 转 dict。"""
    return {
        "id": main.id,
        "name": main.name,
        "change_rate": main.change_rate,
        "children": [sector_data_to_dict(c) for c in main.children],
    }


if __name__ == "__main__":
    repo = SectorRepository()
    print("== 板块层级 ==")
    for main in repo.get_sector_tree():
        print(f"{main.id}({main.name}): {main.change_rate}")
        for child in main.children:
            print(f"    {child.id}({child.name}): {child.change_rate} etfs={len(child.etfs)}")
