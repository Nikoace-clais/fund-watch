"""Portfolio aggregation endpoints: summary, stock X-ray, and value history."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends

from ..core import resolve_portfolio
from ..db import get_request_conn
from ..services.portfolio_service import (
    compute_history,
    compute_holdings_xray,
    compute_summary,
)

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio/summary")
async def portfolio_summary(
    portfolio_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    """Aggregated portfolio stats for a specific portfolio."""
    pf_id = resolve_portfolio(conn, portfolio_id)
    return await compute_summary(conn, pf_id)


@router.get("/api/portfolio/holdings")
async def portfolio_holdings(
    portfolio_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    """Stock-level X-ray: aggregate top-10 holdings across portfolio funds."""
    pf_id = resolve_portfolio(conn, portfolio_id)
    return await compute_holdings_xray(conn, pf_id)


@router.get("/api/portfolio/history")
async def portfolio_history(
    portfolio_id: int | None = None,
    limit: int = 90,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    """Portfolio value history: holdings × NAV per date, plus today's estimate."""
    pf_id = resolve_portfolio(conn, portfolio_id)
    return await compute_history(conn, pf_id, limit)
