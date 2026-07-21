"""Snapshot pulling and the in-process trading-hours scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..core import CST, safe_await, utc_now_iso
from ..db import get_conn, prune_old_snapshots
from ..fund_source import fetch_realtime_estimate
from ..holidays import is_trading_day
from ..repositories import funds_repo, snapshot_repo
from .nav_history import nav_sync_due, sync_pool_nav_history

logger = logging.getLogger(__name__)

cron_state: dict[str, Any] = {
    "last_pull_at": None,
    "pull_count": 0,
    "last_error": None,
    "is_active": False,
}

PULL_INTERVAL_MINUTES = 5
TRADING_HOURS_LABEL = "09:25-11:35, 12:55-15:05 CST (交易日)"
_MORNING_START, _MORNING_END = 9 * 60 + 25, 11 * 60 + 35
_AFTERNOON_START, _AFTERNOON_END = 12 * 60 + 55, 15 * 60 + 5

# 后台净值同步任务的强引用集合：event loop 只弱引用 task，
# 不持引用可能在执行中途被 GC（Python 官方文档建议模式）
_bg_tasks: set[asyncio.Task[None]] = set()


def in_trading_hours() -> bool:
    """True when current CST time is within A-share trading windows (trading days)."""
    now = datetime.now(CST)
    if not is_trading_day(now.date()):  # 周末或法定节假日,不空拉
        return False
    t = now.hour * 60 + now.minute
    morning = _MORNING_START <= t <= _MORNING_END
    afternoon = _AFTERNOON_START <= t <= _AFTERNOON_END
    return morning or afternoon


async def pull_all_snapshots() -> dict[str, Any]:
    """Fetch realtime estimates for every watched fund and persist them."""
    with get_conn() as conn:
        codes = funds_repo.list_codes(conn)

    captured_at = utc_now_iso()

    async def _safe_fetch(code: str) -> tuple[str, dict[str, Any] | None]:
        return code, await safe_await(fetch_realtime_estimate(code))

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


async def _run_nav_history_sync() -> None:
    """后台跑全池净值历史同步；结果记日志，异常不冒出任务边界。"""
    result = await safe_await(sync_pool_nav_history(), log="cron: 净值历史同步异常")
    if result is not None:
        logger.info(
            "cron: 净值历史同步完成 — synced=%d, failed=%d",
            result["synced"],
            result["failed"],
        )


async def snapshot_scheduler() -> None:
    """Background loop: pull snapshots every 5 min during trading hours.

    每日一次（启动时与跨天时）：分层清理旧快照（每日收盘一条永久保留，
    盘中快照保留 30 天）；若当日已到净值同步时点（交易日 15:30 后）则后台
    触发全池净值历史同步——启动首轮循环同样检查，白天重启可补同步。
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
                logger.info(
                    "cron: pruned %d intraday snapshots (每日收盘快照永久保留)", deleted
                )
            except Exception as exc:
                logger.warning("cron: prune failed — %s", exc)
            # create_task 后台跑，不阻塞主拉取循环
            if nav_sync_due(now_cst):
                task = asyncio.create_task(_run_nav_history_sync())
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
            last_prune_day = now_cst.day

        in_hours = in_trading_hours()
        cron_state["is_active"] = in_hours
        if in_hours:
            try:
                result = await pull_all_snapshots()
                cron_state["last_pull_at"] = utc_now_iso()
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
