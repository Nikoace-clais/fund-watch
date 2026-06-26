"""Realtime quotes, intraday snapshots, and scheduler status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core import validate_code
from ..db import get_conn
from ..fund_source import fetch_realtime_estimate
from ..services.snapshots import cron_state, pull_all_snapshots

router = APIRouter(tags=["quotes"])


@router.get("/api/quote/{code}")
async def quote(code: str) -> dict:
    code = validate_code(code)
    try:
        data = await fetch_realtime_estimate(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return data


@router.post("/api/snapshots/pull")
async def pull_snapshots() -> dict:
    return await pull_all_snapshots()


@router.get("/api/snapshots/{code}")
def get_snapshots(code: str, limit: int = 50) -> dict:
    code = validate_code(code)
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT code,name,dwjz,gsz,gszzl,gztime,captured_at
            FROM fund_snapshots
            WHERE code=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (code, limit),
        ).fetchall()
    items = [dict(r) for r in rows]
    items.reverse()
    return {"code": code, "count": len(items), "items": items}


@router.get("/api/cron/status")
def cron_status() -> dict:
    """Return the snapshot scheduler state."""
    return {
        "interval_minutes": 5,
        "trading_hours": "09:25-11:35, 12:55-15:05 CST (周一至周五)",
        **cron_state,
    }
