"""SQL for the funds table (global fund registry)."""

from __future__ import annotations

import sqlite3


def list_funds(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT code, name, sector, created_at FROM funds ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def list_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT code FROM funds").fetchall()
    return [r["code"] for r in rows]


def get_fund(conn: sqlite3.Connection, code: str) -> dict | None:
    row = conn.execute(
        "SELECT code, name, sector, created_at FROM funds WHERE code=?", (code,)
    ).fetchone()
    return dict(row) if row else None


def has_sector(conn: sqlite3.Connection, code: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM funds WHERE code=? AND sector IS NOT NULL", (code,)
        ).fetchone()
        is not None
    )


def upsert_registry(
    conn: sqlite3.Connection,
    code: str,
    name: str | None,
    sector: str | None,
    created_at: str,
) -> None:
    """Insert the fund if new; otherwise fill in name/sector only if provided."""
    existing = get_fund(conn, code)
    if not existing:
        conn.execute(
            "INSERT INTO funds(code, name, sector, created_at) VALUES(?,?,?,?)",
            (code, name, sector, created_at),
        )
        return
    updates, params = [], []
    if name:
        updates.append("name=?")
        params.append(name)
    if sector:
        updates.append("sector=?")
        params.append(sector)
    if updates:
        params.append(code)
        conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)


def delete(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("DELETE FROM funds WHERE code=?", (code,))
