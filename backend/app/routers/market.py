"""Market indices."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..fund_source import fetch_market_indices

router = APIRouter(tags=["market"])


@router.get("/api/market/indices")
async def market_indices() -> dict:
    """Major domestic and overseas market indices from eastmoney."""
    try:
        items = await fetch_market_indices()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"items": items}
