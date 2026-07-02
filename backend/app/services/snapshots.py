"""Snapshot pulling and the in-process trading-hours scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ..core import CST
from ..db import get_conn, prune_old_snapshots
from ..fund_source import fetch_realtime_estimate
from ..repositories import funds_repo, snapshot_repo

logger = logging.getLogger(__name__)

cron_state: dict = {
    "last_pull_at": None,
    "pull_count": 0,
    "last_error": None,
    "is_active": False,
}

PULL_INTERVAL_MINUTES = 5
TRADING_HOURS_LABEL = "09:25-11:35, 12:55-15:05 CST (周一至周五)"
_MORNING_START, _MORNING_END = 9 * 60 + 25, 11 * 60 + 35
_AFTERNOON_START, _AFTERNOON_END = 12 * 60 + 55, 15 * 60 + 5


def in_trading_hours() -> bool:
    """True when current CST time is within A-share trading windows (weekdays)."""
    now = datetime.now(CST)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    t = now.hour * 60 + now.minute
    morning = _MORNING_START <= t <= _MORNING_END
    afternoon = _AFTERNOON_START <= t <= _AFTERNOON_END
    return morning or afternoon


async def pull_all_snapshots() -> dict:
    """Fetch realtime estimates for every watched fund and persist them."""
    with get_conn() as conn:
        codes = funds_repo.list_codes(conn)

    captured_at = datetime.now(timezone.utc).isoformat()

    async def _safe_fetch(code: str) -> tuple[str, dict | None]:
        try:
            return code, await fetch_realtime_estimate(code)
        except Exception:
            return code, None

    results = await asyncio.gather(*[_safe_fetch(c) for c in codes])

    inserted = 0
    with get_conn() as conn:
        for code, d in results:
            if d is None:
                continue
            snapshot_repo.insert(
                conn,
                code=code,
                name=d.get("name"),
                dwjz=d.get("dwjz"),
                gsz=d.get("gsz"),
                gszzl=d.get("gszzl"),
                gztime=d.get("gztime"),
                captured_at=captured_at,
            )
            inserted += 1
        conn.commit()

    return {
        "ok": True,
        "codes": len(codes),
        "inserted": inserted,
        "captured_at": captured_at,
    }


async def snapshot_scheduler() -> None:
    """Background loop: pull snapshots every 5 min during trading hours.
    Also prunes snapshots older than 30 days once per day at startup and at midnight.
    """
    await asyncio.sleep(15)  # startup buffer
    logger.info("cron: scheduler started (interval=5min, trading-hours only)")
    last_prune_day: int = -1
    while True:
        now_cst = datetime.now(CST)
        # I3 fix: prune old snapshots once per calendar day
        if now_cst.day != last_prune_day:
            try:
                deleted = prune_old_snapshots(keep_days=30)
                logger.info("cron: pruned %d old snapshots (keep_days=30)", deleted)
            except Exception as exc:
                logger.warning("cron: prune failed — %s", exc)
            last_prune_day = now_cst.day

        in_hours = in_trading_hours()
        cron_state["is_active"] = in_hours
        if in_hours:
            try:
                result = await pull_all_snapshots()
                cron_state["last_pull_at"] = datetime.now(timezone.utc).isoformat()
                cron_state["pull_count"] += 1
                cron_state["last_error"] = None
                logger.info(
                    "cron: pull done — inserted=%s, total=%d",
                    result.get("inserted"),
                    cron_state["pull_count"],
                )
            except Exception as exc:
                cron_state["last_error"] = str(exc)
                logger.error("cron: pull failed — %s", exc)
        await asyncio.sleep(PULL_INTERVAL_MINUTES * 60)
