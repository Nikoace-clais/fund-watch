"""净值历史服务：DB 优先读取、增量落库与全池每日同步。

数据流：fund_source.fetch_nav_history（东财 pingzhongdata）→
nav_history_repo 落库 fund_nav_history → 读取侧一律从 DB 出数。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from ..core import CST, fetch_502, safe_await
from ..db import get_conn
from ..fund_source import fetch_nav_history
from ..holidays import is_trading_day
from ..repositories import funds_repo, nav_history_repo

logger = logging.getLogger(__name__)

# 落库要全量历史：fetch_nav_history 的 limit 只是返回切片，给个足够大的值即全量
_FULL_HISTORY_LIMIT = 100_000
# A 股收盘后净值公布的稳妥时点（CST 15:30）
_NAV_PUBLISH_MINUTES = 15 * 60 + 30


def nav_sync_due(now: datetime) -> bool:
    """当前 CST 是否已到当日净值同步时点：交易日且已过 15:30。"""
    return (
        is_trading_day(now.date())
        and now.hour * 60 + now.minute >= _NAV_PUBLISH_MINUTES
    )


def _should_refresh(latest: str | None, now: datetime) -> bool:
    """是否需要从上游刷新净值历史。

    - DB 为空：必须拉（首次建底）。
    - 已到当日净值同步时点且 latest_date 落后于今天：增量刷新。
    - 非交易日或盘中：不强制刷新（当日净值尚未公布，拉了也是旧数据）。
    """
    if latest is None:
        return True
    if not nav_sync_due(now):
        return False
    return latest < now.date().isoformat()


async def get_nav_history(
    conn: sqlite3.Connection, code: str, limit: int
) -> list[dict[str, Any]]:
    """DB 优先的净值历史读取；需要刷新时拉上游全量落库后读 DB 返回。

    返回项形状 {date, nav, accNav, dailyReturn}（accNav/dailyReturn 源缺则为 None）。
    """
    latest = nav_history_repo.latest_date(conn, code)
    if _should_refresh(latest, datetime.now(CST)):
        rows = await fetch_502(fetch_nav_history(code, limit=_FULL_HISTORY_LIMIT))
        nav_history_repo.upsert_many(conn, code, rows)
    return nav_history_repo.list_range(conn, code, limit)


async def _sync_one(code: str) -> bool:
    """增量同步一只基金的净值历史；返回是否实际拉取了上游。"""
    with get_conn() as conn:
        latest = nav_history_repo.latest_date(conn, code)
        if not _should_refresh(latest, datetime.now(CST)):
            return False
        rows = await fetch_nav_history(code, limit=_FULL_HISTORY_LIMIT)
        nav_history_repo.upsert_many(conn, code, rows)
        conn.commit()
        return True


async def sync_pool_nav_history() -> dict[str, int]:
    """全池逐只增量同步净值历史。

    单只失败 safe_await 降级记日志不阻塞整池；
    返回 {synced, failed}：synced=实际拉取只数，failed=异常只数（无需刷新的不计）。
    """
    with get_conn() as conn:
        codes = funds_repo.list_codes(conn)

    synced = 0
    failed = 0
    for code in codes:
        result = await safe_await(_sync_one(code), log=f"净值历史同步失败 [{code}]")
        if result is None:
            failed += 1
        elif result:
            synced += 1
    logger.info("净值历史全池同步完成: synced=%d failed=%d", synced, failed)
    return {"synced": synced, "failed": failed}
