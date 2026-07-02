"""SQL for the fund_snapshots table."""

from __future__ import annotations

import sqlite3


def latest(conn: sqlite3.Connection, code: str) -> dict | None:
    row = conn.execute(
        "SELECT code,name,gsz,gszzl,gztime,captured_at"
        " FROM fund_snapshots WHERE code=? ORDER BY id DESC LIMIT 1",
        (code,),
    ).fetchone()
    return dict(row) if row else None


def latest_bulk(conn: sqlite3.Connection, codes: list[str]) -> dict[str, dict]:
    """Latest snapshot per code, one query for the whole batch (no N+1)."""
    if not codes:
        return {}
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        f"""SELECT code,name,gsz,gszzl,gztime,captured_at FROM fund_snapshots
            WHERE id IN (
                SELECT MAX(id) FROM fund_snapshots
                WHERE code IN ({placeholders}) GROUP BY code
            )""",
        codes,
    ).fetchall()
    return {r["code"]: dict(r) for r in rows}


def insert(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str | None,
    dwjz: float | None,
    gsz: float | None,
    gszzl: float | None,
    gztime: str | None,
    captured_at: str,
) -> None:
    conn.execute(
        "INSERT INTO fund_snapshots(code,name,dwjz,gsz,gszzl,gztime,captured_at)"
        " VALUES(?,?,?,?,?,?,?)",
        (code, name, dwjz, gsz, gszzl, gztime, captured_at),
    )


def list_by_code(conn: sqlite3.Connection, code: str, limit: int) -> list[dict]:
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
    return [dict(r) for r in rows]


def delete_all_for_code(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("DELETE FROM fund_snapshots WHERE code=?", (code,))


def prune_older_than(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    cur = conn.execute(
        "DELETE FROM fund_snapshots WHERE captured_at < ?", (cutoff_iso,)
    )
    return cur.rowcount
