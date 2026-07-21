"""SQL for the fund_nav_history table (每日净值历史底座)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..core import utc_now_iso


def upsert_many(conn: sqlite3.Connection, code: str, rows: list[dict[str, Any]]) -> int:
    """批量 INSERT OR REPLACE 净值历史；返回写入条数。

    rows 形状与 fund_source.fetch_nav_history 返回一致
    （{date, nav, accNav, dailyReturn}），落 date/nav/accNav/dailyReturn；
    date 或 nav 为空的脏行跳过。主键 (code, date)，同日重复写即覆盖。
    """
    captured_at = utc_now_iso()
    params = [
        (code, r["date"], r["nav"], r.get("accNav"), r.get("dailyReturn"), captured_at)
        for r in rows
        if r.get("date") and r.get("nav") is not None
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO fund_nav_history"
        "(code, date, nav, acc_nav, daily_return, captured_at)"
        " VALUES(?,?,?,?,?,?)",
        params,
    )
    return len(params)


def list_range(conn: sqlite3.Connection, code: str, limit: int) -> list[dict[str, Any]]:
    """按 date 升序返回最近 limit 条（与上游 fetch_nav_history 的切片语义一致）。"""
    rows = conn.execute(
        """
        SELECT date, nav, acc_nav, daily_return FROM (
            SELECT date, nav, acc_nav, daily_return
            FROM fund_nav_history
            WHERE code=?
            ORDER BY date DESC
            LIMIT ?
        ) ORDER BY date ASC
        """,
        (code, limit),
    ).fetchall()
    return [
        {
            "date": r["date"],
            "nav": r["nav"],
            "accNav": r["acc_nav"],
            "dailyReturn": r["daily_return"],
        }
        for r in rows
    ]


def latest_date(conn: sqlite3.Connection, code: str) -> str | None:
    """增量锚点：库内该基金最新净值日期；无数据返回 None。"""
    row = conn.execute(
        "SELECT MAX(date) AS d FROM fund_nav_history WHERE code=?", (code,)
    ).fetchone()
    return row["d"] if row else None
