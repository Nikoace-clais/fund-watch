"""SQL for the portfolios table."""

from __future__ import annotations

import sqlite3


def list_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT p.id, p.name, p.created_at,
                  COUNT(pos.id) AS fund_count
           FROM portfolios p
           LEFT JOIN positions pos ON pos.portfolio_id = p.id
           GROUP BY p.id ORDER BY p.created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def exists(conn: sqlite3.Connection, portfolio_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM portfolios WHERE id=?", (portfolio_id,)
        ).fetchone()
        is not None
    )


def first_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM portfolios ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def create(conn: sqlite3.Connection, name: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO portfolios(name, created_at) VALUES(?, ?)", (name, created_at)
    )
    return cur.lastrowid  # type: ignore[return-value]


def rename(conn: sqlite3.Connection, portfolio_id: int, name: str) -> None:
    conn.execute("UPDATE portfolios SET name=? WHERE id=?", (name, portfolio_id))


def delete(conn: sqlite3.Connection, portfolio_id: int) -> None:
    conn.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
