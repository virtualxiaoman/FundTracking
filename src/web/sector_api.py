"""
板块涨跌幅 - FastAPI 路由。

提供:
    GET /api/sectors/tree     板块树(主板块 → 子板块 → ETF明细)及涨跌幅
    GET /api/sectors/flatten  平铺的所有子板块涨跌幅列表

可选参数 date=YYYY-MM-DD 查询指定交易日的历史板块数据(读取 etf/ 归档)。
不指定则返回最新 spot 快照数据。

不修改 src/funds 与 src/config 下的任何已有代码。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.sectors.sector_data import SectorRepository, main_sector_to_dict, sector_data_to_dict


def create_sector_router(repo: SectorRepository) -> APIRouter:
    """创建板块路由，注入共享的板块仓库。"""
    router = APIRouter(prefix="/api/sectors", tags=["sectors"])

    @router.get("/tree")
    def get_sector_tree(date: str | None = Query(None, alias="date")):
        """主板块 → 子板块层级涨跌幅。"""
        try:
            sectors = repo.get_sector_tree(trade_date=date)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"该交易日无板块数据: {date} ({e})")
        return {"sectors": [main_sector_to_dict(m) for m in sectors]}

    @router.get("/flatten")
    def get_flatten_sectors(date: str | None = Query(None, alias="date")):
        """平铺所有子板块涨跌幅。"""
        try:
            sectors = repo.get_flatten_sectors(trade_date=date)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"该交易日无板块数据: {date} ({e})")
        return {"sectors": [sector_data_to_dict(s) for s in sectors]}

    return router

