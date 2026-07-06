"""Fund pool management, search, and per-fund data endpoints."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core import fetch_502, validate_code
from ..db import get_request_conn
from ..fund_source import (
    fetch_fund_detail,
    fetch_fund_holdings,
    fetch_fund_info,
    fetch_nav_history,
    fetch_nav_on_date,
    fetch_realtime_estimate,
    search_fund_by_name,
)
from ..repositories import (
    funds_repo,
    portfolios_repo,
    positions_repo,
    snapshot_repo,
    tx_repo,
)
from ..schemas import BatchFundsPayload
from ..services.fund_import import import_funds_batch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["funds"])


@router.get("/api/funds")
def list_funds(conn: sqlite3.Connection = Depends(get_request_conn)) -> dict:
    return {"items": funds_repo.list_funds(conn)}


@router.get("/api/funds/overview")
async def funds_overview(conn: sqlite3.Connection = Depends(get_request_conn)) -> dict:
    funds = funds_repo.list_funds(conn)
    codes = [f["code"] for f in funds]

    t0 = time.perf_counter()

    snapshot_map = snapshot_repo.latest_bulk(conn, codes)
    tx_count_map = tx_repo.count_bulk_for_codes(conn, codes)

    async def _fetch_one(f: dict) -> dict:
        code = f["code"]
        latest_snapshot = snapshot_map.get(code)

        if latest_snapshot is None:
            try:
                q = await fetch_realtime_estimate(code)
                latest_snapshot = {
                    "code": code,
                    "name": q.get("name"),
                    "gsz": q.get("gsz"),
                    "gszzl": q.get("gszzl"),
                    "gztime": q.get("gztime"),
                    "captured_at": None,
                }
            except Exception:
                latest_snapshot = None

        return {
            "fund": f,
            "latest": latest_snapshot,
            "has_transactions": tx_count_map.get(code, 0) > 0,
        }

    items = list(await asyncio.gather(*[_fetch_one(f) for f in funds]))
    logger.info(
        "funds_overview: %d funds fetched in %.3fs",
        len(funds),
        time.perf_counter() - t0,
    )
    return {"items": items}


@router.get("/api/funds/search")
async def search_funds(q: str = "") -> dict:
    """Search funds by name or code keyword via eastmoney."""
    q = q.strip()
    if not q:
        return {"results": []}
    if len(q) > 50:
        raise HTTPException(status_code=400, detail="搜索词过长（最多 50 个字符）")
    try:
        results = await search_fund_by_name(q, limit=20)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"基金搜索源（eastmoney）请求失败: {exc}"
        )
    return {"results": results}


@router.post("/api/funds/batch")
async def add_funds_batch(
    payload: BatchFundsPayload, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict:
    return await import_funds_batch(conn, payload)


@router.post("/api/funds/{code}")
async def add_fund(
    code: str, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict:
    """Add a fund to the global registry (watchlist).

    Position data lives in /api/funds/batch.
    """
    code = validate_code(code)
    now = datetime.now(timezone.utc).isoformat()

    # Fetch fund info (name + sector) from data source
    name = None
    sector = None
    try:
        info = await fetch_fund_info(code)
        name = info.get("name")
        sector = info.get("sector")
    except Exception:
        pass

    existing = funds_repo.get_fund(conn, code)
    if existing:
        if sector and not funds_repo.has_sector(conn, code):
            funds_repo.upsert_registry(conn, code, name, sector, now)
    else:
        if name is None:
            raise HTTPException(
                status_code=400, detail="无法获取基金信息，请确认基金代码有效后重试"
            )
        funds_repo.upsert_registry(conn, code, name, sector, now)
    return {"ok": True, "code": code, "name": name, "sector": sector}


@router.delete("/api/funds/{code}")
def delete_fund(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    """Remove a fund from the watchlist."""
    code = validate_code(code)
    if not funds_repo.get_fund(conn, code):
        raise HTTPException(status_code=404, detail="fund not found")
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="portfolio not found")
        tx_repo.delete_scoped(conn, portfolio_id, code)
        positions_repo.delete_scoped(conn, portfolio_id, code)
        return {
            "ok": True,
            "code": code,
            "portfolio_id": portfolio_id,
            "scope": "portfolio",
        }
    snapshot_repo.delete_all_for_code(conn, code)
    tx_repo.delete_all_for_code(conn, code)
    positions_repo.delete_all_for_code(conn, code)
    funds_repo.delete(conn, code)
    return {"ok": True, "code": code, "scope": "global"}


@router.get("/api/funds/{code}/holdings")
async def get_fund_holdings(code: str) -> dict:
    code = validate_code(code)
    holdings = await fetch_502(fetch_fund_holdings(code))
    return {"code": code, "count": len(holdings), "holdings": holdings}


@router.get("/api/funds/{code}/detail")
async def get_fund_detail(code: str) -> dict:
    """Comprehensive fund detail: manager, size, period returns, asset allocation."""
    code = validate_code(code)
    return await fetch_502(fetch_fund_detail(code))


@router.get("/api/funds/{code}/nav-history")
async def get_nav_history(code: str, limit: int = 365) -> dict:
    """Historical NAV data for charting."""
    code = validate_code(code)
    limit = max(1, min(limit, 1000))
    history = await fetch_502(fetch_nav_history(code, limit=limit))
    return {"code": code, "count": len(history), "history": history}


@router.get("/api/funds/{code}/nav-on")
async def get_nav_on_date(code: str, date: str) -> dict:
    """Return the NAV for a specific date (YYYY-MM-DD)."""
    code = validate_code(code)
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date 必须是有效的 YYYY-MM-DD 日期")
    nav = await fetch_502(fetch_nav_on_date(code, date))
    return {"code": code, "date": date, "nav": nav}
