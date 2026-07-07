"""SQL for the positions table (per-portfolio fund holdings)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any


def ensure_exists(
    conn: sqlite3.Connection, portfolio_id: int, code: str, created_at: str
) -> None:
    """Create an empty position row if one doesn't exist yet (idempotent)."""
    conn.execute(
        "INSERT OR IGNORE INTO positions(portfolio_id, code, created_at)"
        " VALUES(?, ?, ?)",
        (portfolio_id, code, created_at),
    )


def upsert(
    conn: sqlite3.Connection,
    portfolio_id: int,
    code: str,
    created_at: str,
    *,
    # ponytail: float, not Decimal — these are user-entered/estimated import
    # amounts, not the ledger (transactions.amount is TEXT/Decimal already).
    # Switch to Decimal-as-TEXT if these ever feed a precision-sensitive calc.
    amount: float | None = None,
    imported_holding_amount: float | None = None,
    imported_cumulative_return: float | None = None,
    imported_holding_return: float | None = None,
) -> None:
    """Insert the position if new; otherwise update only the given fields.

    ponytail: INSERT OR IGNORE + UPDATE instead of get()-then-branch, so two
    concurrent imports of the same (portfolio_id, code) can't both see "not
    found" and double-insert.
    """
    conn.execute(
        "INSERT OR IGNORE INTO positions(portfolio_id, code, created_at)"
        " VALUES(?, ?, ?)",
        (portfolio_id, code, created_at),
    )
    updates: list[str] = []
    params: list[Any] = []
    if amount is not None:
        updates.append("amount=?")
        params.append(amount)
    if imported_holding_amount is not None:
        updates.append("imported_holding_amount=?")
        params.append(imported_holding_amount)
    if imported_cumulative_return is not None:
        updates.append("imported_cumulative_return=?")
        params.append(imported_cumulative_return)
    if imported_holding_return is not None:
        updates.append("imported_holding_return=?")
        params.append(imported_holding_return)
    if updates:
        params += [portfolio_id, code]
        conn.execute(
            f"UPDATE positions SET {','.join(updates)}"
            " WHERE portfolio_id=? AND code=?",
            params,
        )


def set_holding_shares(
    conn: sqlite3.Connection, portfolio_id: int, code: str, value: str | None
) -> None:
    conn.execute(
        "UPDATE positions SET holding_shares=? WHERE portfolio_id=? AND code=?",
        (value, portfolio_id, code),
    )


def delete_scoped(conn: sqlite3.Connection, portfolio_id: int, code: str) -> None:
    conn.execute(
        "DELETE FROM positions WHERE portfolio_id=? AND code=?", (portfolio_id, code)
    )


def delete_all_for_portfolio(conn: sqlite3.Connection, portfolio_id: int) -> None:
    conn.execute("DELETE FROM positions WHERE portfolio_id=?", (portfolio_id,))


def delete_all_for_code(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("DELETE FROM positions WHERE code=?", (code,))


def list_holdings_with_shares(
    conn: sqlite3.Connection, portfolio_id: int
) -> list[dict[str, Any]]:
    """Positions with a computed holding (have transactions), joined to fund name."""
    rows = conn.execute(
        """SELECT pos.code, f.name, pos.holding_shares
           FROM positions pos
           JOIN funds f ON f.code = pos.code
           WHERE pos.portfolio_id=? AND pos.holding_shares IS NOT NULL
           ORDER BY pos.created_at DESC""",
        (portfolio_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_imported_positions(
    conn: sqlite3.Connection, portfolio_id: int
) -> list[dict[str, Any]]:
    """Imported positions without transactions (holding_amount > 0)."""
    rows = conn.execute(
        """SELECT pos.code, f.name,
              COALESCE(pos.imported_holding_amount, pos.amount) AS holding_amount,
              pos.imported_cumulative_return,
              pos.imported_holding_return
           FROM positions pos
           JOIN funds f ON f.code = pos.code
           WHERE pos.portfolio_id=?
             AND pos.holding_shares IS NULL
             AND COALESCE(pos.imported_holding_amount, pos.amount) > 0
           ORDER BY pos.created_at DESC""",
        (portfolio_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_watch_only_codes(conn: sqlite3.Connection, portfolio_id: int) -> list[str]:
    """Positions with neither transactions nor an imported amount (watch-only)."""
    rows = conn.execute(
        """SELECT pos.code FROM positions pos
           WHERE pos.portfolio_id=?
             AND pos.holding_shares IS NULL
             AND COALESCE(pos.imported_holding_amount, pos.amount, 0) <= 0
           ORDER BY pos.created_at DESC""",
        (portfolio_id,),
    ).fetchall()
    return [r["code"] for r in rows]


def current_holdings(
    conn: sqlite3.Connection, portfolio_id: int
) -> dict[str, Decimal]:
    """code -> holding_shares for positions with a positive computed holding."""
    rows = conn.execute(
        "SELECT code, holding_shares FROM positions"
        " WHERE portfolio_id=? AND holding_shares IS NOT NULL",
        (portfolio_id,),
    ).fetchall()
    return {
        r["code"]: Decimal(r["holding_shares"])
        for r in rows
        if r["holding_shares"] and Decimal(r["holding_shares"]) > 0
    }


def imported_amounts(
    conn: sqlite3.Connection, portfolio_id: int
) -> dict[str, Decimal]:
    """code -> imported holding amount, for positions without transactions."""
    rows = conn.execute(
        """SELECT code,
              COALESCE(imported_holding_amount, amount) AS holding_amount
           FROM positions WHERE portfolio_id=? AND holding_shares IS NULL
           AND COALESCE(imported_holding_amount, amount) > 0""",
        (portfolio_id,),
    ).fetchall()
    return {r["code"]: Decimal(str(r["holding_amount"])) for r in rows}
