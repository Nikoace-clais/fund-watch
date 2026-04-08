"""Fund API router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..external import fetch_fund_detail, fetch_fund_holdings, fetch_nav_history, fetch_realtime_estimate, search_fund_by_name
from ..models.schemas import FundBatchImport, FundCreate
from ..services.fund_service import FundService

router = APIRouter(prefix="/api", tags=["funds"])

# Service instance (could be dependency injected)
fund_service = FundService()


@router.get("/funds")
async def list_funds() -> dict[str, Any]:
    """List all funds in pool."""
    funds = fund_service.get_funds()
    return {"items": funds}


@router.post("/funds/{code}")
async def add_fund(code: str) -> dict[str, Any]:
    """Add a single fund to pool."""
    # Validate code format
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="Invalid fund code format")
    
    fund = await fund_service.create_fund(code)
    return {"ok": True, "fund": fund}


@router.post("/funds/batch")
async def batch_add_funds(data: FundBatchImport) -> dict[str, Any]:
    """Batch add funds."""
    result = fund_service.batch_create(data.codes)
    return {
        "ok": True,
        "added": result["inserted"],
        "total": result["total"],
    }


@router.delete("/funds/{code}")
async def delete_fund(code: str) -> dict[str, Any]:
    """Delete fund from pool."""
    success = fund_service.delete_fund(code)
    if not success:
        raise HTTPException(status_code=404, detail="Fund not found")
    return {"ok": True}


@router.get("/funds/overview")
async def funds_overview() -> dict[str, Any]:
    """Get fund pool overview with latest quotes."""
    funds = fund_service.get_funds()
    items = []
    for fund in funds:
        try:
            quote = await fetch_realtime_estimate(fund["code"])
        except Exception:
            quote = None
        items.append({
            "fund": fund,
            "latest": quote,
        })
    return {"items": items}


@router.get("/funds/search")
async def search_funds(q: str, limit: int = 5) -> dict[str, Any]:
    """Search funds by name/code."""
    results = await search_fund_by_name(q, limit=limit)
    return {"results": results}


@router.get("/funds/{code}/detail")
async def fund_detail(code: str) -> dict[str, Any]:
    """Get fund detail."""
    detail = await fetch_fund_detail(code)
    return detail


@router.get("/funds/{code}/holdings")
async def fund_holdings(code: str) -> dict[str, Any]:
    """Get fund top 10 holdings."""
    holdings = await fetch_fund_holdings(code)
    return {"code": code, "count": len(holdings), "holdings": holdings}


@router.get("/funds/{code}/nav-history")
async def fund_nav_history(code: str, limit: int = 365) -> dict[str, Any]:
    """Get fund NAV history."""
    history = await fetch_nav_history(code, limit=limit)
    return {"code": code, "count": len(history), "history": history}


@router.get("/quote/{code}")
async def get_quote(code: str) -> dict[str, Any]:
    """Get real-time quote for a fund."""
    try:
        quote = await fetch_realtime_estimate(code)
        return quote
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch quote: {e}")
