"""SQL for the fund_snapshots table."""

from __future__ import annotations

import sqlite3
from typing import Any


def latest_bulk(
    conn: sqlite3.Connection, codes: list[str]
) -> dict[str, dict[str, Any]]:
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


def list_by_code(
    conn: sqlite3.Connection, code: str, limit: int
) -> list[dict[str, Any]]:
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
    """分层保留清理：删除 cutoff 之前的盘中快照，每日收盘快照永久保留。

    每个自然日 id 最大（最接近收盘）的一条快照不删，用于长期历史回溯；
    其余盘中快照超过保留期才清理。

    注意：date(captured_at) 按 UTC 日界分组（captured_at 是 UTC ISO 串），
    与 CST 自然日界最多相差一条边界日的保留快照，属可接受的近似。
    """
    cur = conn.execute(
        """
        DELETE FROM fund_snapshots
        WHERE captured_at < ?
          AND id NOT IN (
              SELECT MAX(id) FROM fund_snapshots GROUP BY date(captured_at)
          )
        """,
        (cutoff_iso,),
    )
    return cur.rowcount
