"""Market indices."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from ..fund_source import fetch_market_indices

logger = logging.getLogger(__name__)

router = APIRouter(tags=["market"])


@router.get("/api/market/indices")
async def market_indices() -> dict:
    """Major domestic and overseas market indices from Sina Finance."""
    try:
        items = await fetch_market_indices()
    except Exception as exc:
        logger.warning("Failed to fetch market indices: %s", exc)
        # Return empty items on failure so frontend doesn't break
        return {"items": [], "error": "暂时无法获取行情数据，请稍后重试"}
    return {"items": items}
