"""SQL for the transactions table."""

from __future__ import annotations

import sqlite3
from datetime import datetime


def insert(
    conn: sqlite3.Connection,
    *,
    code: str,
    portfolio_id: int,
    direction: str,
    trade_date: str,
    nav: str,
    shares: str,
    amount: str,
    fee: str = "0",
    note: str | None = None,
    source: str,
    created_at: str,
) -> None:
    """The one INSERT shared by manual entry, CSV import, and synthetic buys."""
    if not (code.isdigit() and len(code) == 6):
        raise ValueError(f"invalid fund code: {code}")
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"invalid trade_date: {trade_date}")
    conn.execute(
        "INSERT INTO transactions"
        "(code,portfolio_id,direction,trade_date,nav,shares,amount,fee,note,source,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            code,
            portfolio_id,
            direction,
            trade_date,
            nav,
            shares,
            amount,
            fee,
            note,
            source,
            created_at,
        ),
    )


def list_by_code(conn: sqlite3.Connection, portfolio_id: int, code: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions"
        " WHERE portfolio_id=? AND code=? ORDER BY trade_date DESC, id DESC",
        (portfolio_id, code),
    ).fetchall()
    return [dict(r) for r in rows]


def list_shares_by_direction(
    conn: sqlite3.Connection, portfolio_id: int, code: str
) -> list[dict]:
    """direction+shares rows for a (portfolio, code), used to net the holding."""
    rows = conn.execute(
        "SELECT direction, shares FROM transactions WHERE portfolio_id=? AND code=?",
        (portfolio_id, code),
    ).fetchall()
    return [dict(r) for r in rows]


def list_for_pnl(conn: sqlite3.Connection, portfolio_id: int, code: str) -> list[dict]:
    rows = conn.execute(
        "SELECT direction, nav, shares, amount, fee FROM transactions"
        " WHERE portfolio_id=? AND code=? ORDER BY trade_date",
        (portfolio_id, code),
    ).fetchall()
    return [dict(r) for r in rows]


def list_for_pnl_bulk(
    conn: sqlite3.Connection, portfolio_id: int, codes: list[str]
) -> dict[str, list[dict]]:
    """Grouped transaction rows for P&L, one query for the whole batch."""
    if not codes:
        return {}
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        f"SELECT code, direction, nav, shares, amount, fee FROM transactions"
        f" WHERE portfolio_id=? AND code IN ({placeholders}) ORDER BY trade_date",
        (portfolio_id, *codes),
    ).fetchall()
    grouped: dict[str, list[dict]] = {c: [] for c in codes}
    for r in rows:
        grouped[r["code"]].append(dict(r))
    return grouped


def list_for_portfolio(conn: sqlite3.Connection, portfolio_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT code, direction, trade_date, shares"
        " FROM transactions WHERE portfolio_id=? ORDER BY trade_date ASC",
        (portfolio_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get(conn: sqlite3.Connection, tx_id: int) -> dict | None:
    row = conn.execute(
        "SELECT code, portfolio_id, direction, shares FROM transactions WHERE id=?",
        (tx_id,),
    ).fetchone()
    return dict(row) if row else None


def delete(conn: sqlite3.Connection, tx_id: int) -> None:
    conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))


def delete_scoped(conn: sqlite3.Connection, portfolio_id: int, code: str) -> None:
    conn.execute(
        "DELETE FROM transactions WHERE portfolio_id=? AND code=?",
        (portfolio_id, code),
    )


def delete_all_for_portfolio(conn: sqlite3.Connection, portfolio_id: int) -> None:
    conn.execute("DELETE FROM transactions WHERE portfolio_id=?", (portfolio_id,))


def delete_all_for_code(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("DELETE FROM transactions WHERE code=?", (code,))


def count_for_code(conn: sqlite3.Connection, code: str) -> int:
    """Global transaction count for a fund, across all portfolios."""
    return conn.execute(
        "SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)
    ).fetchone()["c"]


def count_bulk_for_codes(conn: sqlite3.Connection, codes: list[str]) -> dict[str, int]:
    """Global transaction count per code, one query for the whole batch."""
    if not codes:
        return {}
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        f"SELECT code, COUNT(*) as c FROM transactions"
        f" WHERE code IN ({placeholders}) GROUP BY code",
        codes,
    ).fetchall()
    return {r["code"]: r["c"] for r in rows}


def count_for_portfolio_code(
    conn: sqlite3.Connection, portfolio_id: int, code: str
) -> int:
    return conn.execute(
        "SELECT COUNT(*) as c FROM transactions WHERE portfolio_id=? AND code=?",
        (portfolio_id, code),
    ).fetchone()["c"]


def find_duplicate(
    conn: sqlite3.Connection,
    portfolio_id: int,
    code: str,
    direction: str,
    trade_date: str,
    nav: str,
    shares: str,
) -> bool:
    return (
        conn.execute(
            "SELECT id FROM transactions"
            " WHERE portfolio_id=? AND code=?"
            " AND direction=? AND trade_date=? AND nav=? AND shares=?",
            (portfolio_id, code, direction, trade_date, nav, shares),
        ).fetchone()
        is not None
    )
