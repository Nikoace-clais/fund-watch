"""Stock-centric endpoints: reverse-lookup funds holding a stock."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from ..core import validate_code
from ..fund_source import fetch_funds_holding_stock

router = APIRouter(tags=["stocks"])


@router.get("/api/stocks/{code}/funds")
async def funds_holding_stock(code: str, limit: int = 50) -> dict:
    """List public funds that hold *code* (6-digit stock code), by position value."""
    # ponytail: validate_code 复用,股票代码同为 6 位数字
    code = validate_code(code)
    try:
        return await fetch_funds_holding_stock(code, limit=min(limit, 200))
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail=f"股票持仓数据源不可用: {exc}"
        ) from exc
