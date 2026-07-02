"""SQL for the stock_industry table (persisted eastmoney industry lookups)."""

from __future__ import annotations

import sqlite3


def get_bulk(conn: sqlite3.Connection, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        "SELECT stock_code, industry FROM stock_industry"
        f" WHERE stock_code IN ({placeholders})",
        codes,
    ).fetchall()
    return {r["stock_code"]: r["industry"] for r in rows if r["industry"]}


def upsert_bulk(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str | None, str, str]],
) -> None:
    """rows: (stock_code, stock_name, industry, updated_at)."""
    if not rows:
        return
    conn.executemany(
        "INSERT OR REPLACE INTO stock_industry"
        " (stock_code, stock_name, industry, updated_at)"
        " VALUES (?, ?, ?, ?)",
        rows,
    )
