"""Stock-centric endpoints: reverse-lookup funds holding a stock."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..core import fetch_502, validate_code
from ..fund_source import fetch_funds_holding_stock

router = APIRouter(tags=["stocks"])


@router.get("/api/stocks/{code}/funds")
async def funds_holding_stock(
    code: str, limit: int = Query(default=50, ge=1)
) -> dict[str, Any]:
    """List public funds that hold *code* (6-digit stock code), by position value."""
    # ponytail: validate_code 复用,股票代码同为 6 位数字
    code = validate_code(code)
    return await fetch_502(fetch_funds_holding_stock(code, limit=min(limit, 200)))
