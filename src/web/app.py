"""
基金持仓看板 - FastAPI 服务入口。

组合底层已有仓库(FundInfoRepository / FundEstimationRepository /
FundHistoryRepository / HoldingsRepository)对外提供 REST 接口，
并托管前端静态文件(web/dist)。

不修改 src/funds 与 src/config 下的任何已有代码。

启动:
    python -m uvicorn src.web.app:app --reload --port 8000
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config.path import PROJECT_ROOT
from src.funds.estimation.cftao import CftaoEstimationProvider
from src.funds.estimation.eastmoney import EastMoneyEstimationProvider
from src.funds.estimation.sina import SinaEstimationProvider
from src.funds.estimation.tencent import TencentEstimationProvider
from src.funds.exceptions import FundError
from src.funds.fund_data import FundHistoryCache
from src.funds.fund_estimation import FundEstimationRepository
from src.funds.fund_history import FundHistoryRepository
from src.funds.fund_info import FundInfoRepository
from src.portfolio.holdings import HoldingsRepository

app = FastAPI(title="基金持仓看板")

# 开发模式跨域(生产同源部署时不需要，保留无妨)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 全局仓库实例(进程内单例)
# ============================================================
_fund_info = FundInfoRepository()
_fund_history = FundHistoryRepository()
_estimation = FundEstimationRepository(
    providers=[
        EastMoneyEstimationProvider(),
        TencentEstimationProvider(),
        CftaoEstimationProvider(),
        SinaEstimationProvider(),
    ],
    default_source="eastmoney",
    cache_seconds=30,
)
_holdings = HoldingsRepository()


# ============================================================
# 请求/响应模型
# ============================================================

class AddFundRequest(BaseModel):
    fund_code: str


class SetAmountRequest(BaseModel):
    current_amount: float
    profit_amount: float


class TransactionRequest(BaseModel):
    date: date
    amount: float  # >0 加仓，<0 减仓
    update_amount: bool = True  # 是否同时联动 current_amount（加仓加上、减仓扣减）


# ============================================================
# 工具
# ============================================================

def _fund_name(code: str) -> str:
    fund = _fund_info.get_by_code(code)
    return fund.name if fund else code


def _today() -> date:
    return date.today()


def _get_latest_nav(code: str) -> tuple[float | None, float | None, date | None]:
    """
    返回 (昨日单位净值, 今日单位净值, 最新净值日期)
    优先使用已有缓存，自动尝试更新。
    """
    try:
        cache: FundHistoryCache = _fund_history.get_history(code, auto_update=True)
    except Exception:
        try:
            cache: FundHistoryCache = _fund_history.get_history(code, auto_update=False)
        except Exception:
            return None, None, None

    if not cache.items:
        return None, None, None

    last = cache.items[-1]
    if len(cache.items) >= 2:
        prev = cache.items[-2]
    else:
        prev = None

    today_nav = last.unit_nav if last.date >= _today() else None
    yesterday_nav = (prev.unit_nav if prev else None) if today_nav is not None else last.unit_nav

    return yesterday_nav, today_nav, last.date


def _estimation_or_none(code: str) -> dict | None:
    try:
        est = _estimation.get_estimation(code, force=True)
        return {
            "estimate_nav": est.estimate_nav,
            "change_rate": est.change_rate,  # 小数，如 0.0125 表示 +1.25%
            "source": est.source,
            "query_time": est.query_time.isoformat(),
        }
    except FundError:
        return None


# ============================================================
# 首页: 当前持仓卡片
# ============================================================

@app.get("/api/portfolio")
def get_portfolio(force: bool = False):
    """首页卡片数据。force=False 使用估值缓存，force=True 强制刷新估值。"""
    holdings = _holdings.list()
    codes = [h.fund_code for h in holdings]
    estimations = _estimation.get_estimations(codes, force=force) if codes else {}

    cards = []
    for h in holdings:
        code = h.fund_code
        est = estimations.get(code)
        yesterday_nav, today_nav, latest_date = _get_latest_nav(code)
        cards.append({
            "fund_code": code,
            "fund_name": _fund_name(code),
            "yesterday_nav": yesterday_nav,
            "today_nav": today_nav,
            "latest_nav_date": latest_date.isoformat() if latest_date else None,
            "estimation": est,
            "current_amount": h.current_amount,
            "profit_amount": h.profit_amount,
            "transactions": h.transactions,
        })
    return {"cards": cards}


# ============================================================
# 持仓管理
# ============================================================

@app.get("/api/holdings")
def list_holdings():
    """持仓管理页所需的轻量持仓列表（不请求外部数据源）。"""
    return {
        "holdings": [
            {
                "fund_code": h.fund_code,
                "fund_name": _fund_name(h.fund_code),
                "current_amount": h.current_amount,
                "profit_amount": h.profit_amount,
                "transactions": h.transactions,
            }
            for h in _holdings.list()
        ]
    }


@app.post("/api/holdings")
def add_holding(req: AddFundRequest):
    code = req.fund_code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="基金代码不能为空")
    if _fund_info.get_by_code(code) is None:
        raise HTTPException(status_code=404, detail=f"基金不存在: {code}")
    ok = _holdings.add_fund(code)
    if not ok:
        raise HTTPException(status_code=409, detail=f"基金已在持仓中: {code}")
    return {"ok": True, "fund_code": code}


@app.delete("/api/holdings/{fund_code}")
def remove_holding(fund_code: str):
    ok = _holdings.remove_fund(fund_code)
    if not ok:
        raise HTTPException(status_code=404, detail=f"持仓不存在: {fund_code}")
    return {"ok": True}


@app.put("/api/holdings/{fund_code}/amount")
def set_amount(fund_code: str, req: SetAmountRequest):
    ok = _holdings.set_amount(fund_code, req.current_amount, req.profit_amount)
    if not ok:
        raise HTTPException(status_code=404, detail=f"持仓不存在: {fund_code}")
    return {"ok": True}


@app.post("/api/holdings/{fund_code}/transactions")
def add_transaction(fund_code: str, req: TransactionRequest):
    if req.amount == 0:
        raise HTTPException(status_code=422, detail="增减仓金额不能为 0")

    holding = _holdings.get(fund_code)
    if holding is None:
        raise HTTPException(status_code=404, detail=f"持仓不存在: {fund_code}")

    # 加减仓联动当前持仓金额：加仓增加，减仓扣减（最低扣到 0，避免负持仓）
    new_amount = holding.current_amount
    if req.update_amount:
        new_amount = holding.current_amount + req.amount
        if new_amount < 0:
            raise HTTPException(
                status_code=422,
                detail=f"减仓金额 {abs(req.amount):.2f} 元超过当前持仓 {holding.current_amount:.2f} 元，无法减仓",
            )
        _holdings.set_amount(fund_code, new_amount, holding.profit_amount)

    ok = _holdings.add_transaction(fund_code, req.date, req.amount)
    if not ok:
        raise HTTPException(status_code=404, detail=f"持仓不存在: {fund_code}")
    return {"ok": True, "fund_code": fund_code, "current_amount": new_amount}


# ============================================================
# 基金信息
# ============================================================

@app.get("/api/funds/search")
def search_funds(keyword: str = Query(..., min_length=1), limit: int = 20):
    funds = _fund_info.search(keyword, limit=limit)
    return {"results": [{"fund_code": f.code, "fund_name": f.name} for f in funds]}


@app.get("/api/funds/{fund_code}/history")
def fund_history(fund_code: str, range: str = Query("1Y", alias="range")):
    """
    历史净值曲线数据。
    range: 1M / 3M / 6M / 1Y / 3Y / 5Y / ALL
    """
    ranges = {
        "1M": _fund_history.get_last_month_history,
        "3M": _fund_history.get_last_3_months_history,
        "6M": _fund_history.get_last_6_months_history,
        "1Y": _fund_history.get_last_year_history,
        "3Y": _fund_history.get_last_3_years_history,
        "5Y": _fund_history.get_last_5_years_history,
        "ALL": None,
    }
    if range not in ranges:
        raise HTTPException(status_code=422, detail=f"不支持的 range: {range}")

    try:
        if range == "ALL":
            cache = _fund_history.get_history(fund_code, auto_update=True)
        else:
            cache = ranges[range](fund_code)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "fund_code": fund_code,
        "fund_name": _fund_name(fund_code),
        "items": [
            {
                "date": it.date.isoformat(),
                "unit_nav": it.unit_nav,
                "accumulated_nav": it.accumulated_nav,
                "daily_change": it.daily_change,  # 小数，如 0.0125 表示 +1.25%
            }
            for it in cache.items
        ],
    }


@app.get("/api/funds/{fund_code}/nav")
def fund_nav(fund_code: str):
    """昨日净值 / 今日净值 / 今日估值。"""
    yesterday_nav, today_nav, latest_date = _get_latest_nav(fund_code)
    return {
        "fund_code": fund_code,
        "fund_name": _fund_name(fund_code),
        "yesterday_nav": yesterday_nav,
        "today_nav": today_nav,
        "latest_nav_date": latest_date.isoformat() if latest_date else None,
        "estimation": _estimation_or_none(fund_code),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ============================================================
# 前端静态资源(SPA, hash 路由，直接 / 即可)
# ============================================================

WEB_DIST = PROJECT_ROOT / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.web.app:app", host="127.0.0.1", port=8080, reload=False)
