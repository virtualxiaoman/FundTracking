"""
全部基金历史排名 - FastAPI 路由。

提供:
    GET /api/ranking?range=1W&sort=desc&page=1&page_size=50
        range:      TODAY / 1W / 1M / 3M / 1Y / 3Y / 5Y / ALL
        sort:       desc=涨幅从高到低(默认), asc=跌幅从高到低
        page:       页码(从1开始)
        page_size:  每页条数(默认50, 最大500)

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
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
    ):
        """全部基金按指定时间范围的涨跌幅排名（分页）。"""
        if range not in RANGE_MAP:
            raise HTTPException(status_code=422, detail=f"不支持的 range: {range}，可选 {list(RANGE_MAP)}")
        if sort not in ("asc", "desc"):
            raise HTTPException(status_code=422, detail="sort 只能为 asc 或 desc")

        try:
            # 取未分页的完整排序结果，接口层做分页切片
            all_rows = repo.get_ranking(range, sort=sort, limit=None)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"排名查询失败: {e}")

        total = len(all_rows)
        start = (page - 1) * page_size
        page_rows = all_rows[start:start + page_size]

        result = []
        for r in page_rows:
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

        return {
            "range": range,
            "sort": sort,
            "page": page,
            "page_size": page_size,
            "total": total,
            "count": len(result),
            "results": result,
        }

    return router
