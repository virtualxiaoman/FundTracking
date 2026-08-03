"""
全部基金历史排名 - FastAPI 路由。

提供:
    GET /api/ranking?range=1W&sort=desc&limit=20
        range: TODAY / 1W / 1M / 3M / 1Y / 3Y / 5Y / ALL
        sort:  desc=涨幅从高到低(默认), asc=跌幅从高到低

不修改 src/funds 与 src/config 下的任何已有代码。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.funds.fund_info import FundInfoRepository
from src.ranking.repository import RANGE_MAP, FundRankingRepository


def create_ranking_router(repo: FundRankingRepository, fund_info: FundInfoRepository) -> APIRouter:
    """创建排名路由，注入共享的排名仓库与基金信息仓库。"""
    router = APIRouter(prefix="/api", tags=["ranking"])

    @router.get("/ranking")
    def get_ranking(
        range: str = Query("1W", alias="range"),
        sort: str = Query("desc"),
        limit: int = Query(50, ge=1, le=1000),
    ):
        """全部基金按指定时间范围的涨跌幅排名。"""
        if range not in RANGE_MAP:
            raise HTTPException(status_code=422, detail=f"不支持的 range: {range}，可选 {list(RANGE_MAP)}")
        if sort not in ("asc", "desc"):
            raise HTTPException(status_code=422, detail="sort 只能为 asc 或 desc")

        try:
            rows = repo.get_ranking(range, sort=sort, limit=limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"排名查询失败: {e}")

        result = []
        for r in rows:
            fund = fund_info.get_by_code(r["fund_code"])
            if fund is None:
                continue  # 无名称信息的基金不展示
            result.append({
                "fund_code": r["fund_code"],
                "fund_name": fund.name,
                "first_date": r["first_date"],
                "last_date": r["last_date"],
                "first_nav": r["first_nav"],
                "last_nav": r["last_nav"],
                "change_rate": r["change_rate"],  # 小数，如 0.0125 表示 +1.25%
            })

        return {"range": range, "sort": sort, "count": len(result), "results": result}

    return router
