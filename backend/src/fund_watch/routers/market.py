"""Market data router."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from ..external import fetch_market_indices

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/indices")
async def get_market_indices() -> dict[str, Any]:
    """Get major market indices."""
    try:
        items = await fetch_market_indices()
        return {"items": items}
    except Exception as e:
        logger.warning("Failed to fetch market indices: %s", e)
        # Return empty items on failure so frontend doesn't break
        return {"items": [], "error": "暂时无法获取行情数据，请稍后重试"}
