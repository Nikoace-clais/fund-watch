"""Market data router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..external import fetch_market_indices

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/indices")
async def get_market_indices() -> dict[str, Any]:
    """Get major market indices."""
    items = await fetch_market_indices()
    return {"items": items}
