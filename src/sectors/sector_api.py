"""
板块涨跌幅 - FastAPI 路由。

提供:
    GET /api/sectors/tree     板块树(主板块 → 子板块 → ETF明细)及涨跌幅
    GET /api/sectors/flatten  平铺的所有子板块涨跌幅列表

不修改 src/funds 与 src/config 下的任何已有代码。
"""

from __future__ import annotations

from fastapi import APIRouter

from src.sectors.sector_data import SectorRepository, main_sector_to_dict, sector_data_to_dict


def create_sector_router(repo: SectorRepository) -> APIRouter:
    """创建板块路由，注入共享的板块仓库。"""
    router = APIRouter(prefix="/api/sectors", tags=["sectors"])

    @router.get("/tree")
    def get_sector_tree():
        """主板块 → 子板块层级涨跌幅。"""
        return {"sectors": [main_sector_to_dict(m) for m in repo.get_sector_tree()]}

    @router.get("/flatten")
    def get_flatten_sectors():
        """平铺所有子板块涨跌幅。"""
        return {"sectors": [sector_data_to_dict(s) for s in repo.get_flatten_sectors()]}

    return router
