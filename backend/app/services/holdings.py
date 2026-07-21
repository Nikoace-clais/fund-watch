"""Holding shares and P&L computation from the transaction log."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from ..core import q2
from ..repositories import positions_repo, tx_repo


def _net_shares(rows: list[dict[str, Any]]) -> Decimal:
    holding = Decimal("0")
    for r in rows:
        s = Decimal(r["shares"])
        holding += s if r["direction"] == "buy" else -s
    return holding


def current_holding_shares(
    conn: sqlite3.Connection, portfolio_id: int, code: str
) -> Decimal:
    """Net buy/sell shares for a (portfolio_id, code), as currently recorded."""
    return _net_shares(tx_repo.list_shares_by_direction(conn, portfolio_id, code))


def never_negative_when_replayed(
    conn: sqlite3.Connection,
    portfolio_id: int,
    code: str,
    *,
    extra: list[dict[str, Any]] | None = None,
    remove_id: int | None = None,
) -> bool:
    """Replay the tx log by trade_date; True if net shares never go negative.

    `extra` rows ({"direction", "trade_date", "shares"}) are treated as newer
    than stored rows on the same date; `remove_id` excludes one stored row.
    """
    rows = [
        r
        for r in tx_repo.list_chronological(conn, portfolio_id, code)
        if r["id"] != remove_id
    ]
    keyed: list[tuple[str, int, int, dict[str, Any]]] = [
        (r["trade_date"], 0, r["id"], r) for r in rows
    ]
    for i, e in enumerate(extra or []):
        keyed.append((e["trade_date"], 1, i, e))
    keyed.sort(key=lambda t: (t[0], t[1], t[2]))

    net = Decimal("0")
    for _, _, _, r in keyed:
        s = Decimal(r["shares"])
        net += s if r["direction"] == "buy" else -s
        if net < 0:
            return False
    return True


def recompute_holding_shares(
    conn: sqlite3.Connection, portfolio_id: int, code: str
) -> None:
    """Recompute positions.holding_shares from transactions for (portfolio_id, code)."""
    rows = tx_repo.list_shares_by_direction(conn, portfolio_id, code)
    if not rows:
        positions_repo.set_holding_shares(conn, portfolio_id, code, None)
        return
    positions_repo.set_holding_shares(conn, portfolio_id, code, str(_net_shares(rows)))


def compute_pnl(
    conn: sqlite3.Connection,
    portfolio_id: int,
    code: str,
    current_nav: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, str | None]:
    """Compute full P&L (realized + unrealized) for a (portfolio_id, code) position.

    Pass `rows` (e.g. from tx_repo.list_for_pnl_bulk) when the caller already
    has transactions for many codes, to avoid a query per code.
    """
    if rows is None:
        rows = tx_repo.list_for_pnl(conn, portfolio_id, code)

    buy_shares = Decimal("0")
    buy_amount = Decimal("0")
    buy_fee = Decimal("0")
    sell_shares = Decimal("0")
    sell_amount = Decimal("0")
    sell_fee = Decimal("0")

    for r in rows:
        s = Decimal(r["shares"])
        a = Decimal(r["amount"])
        f = Decimal(r["fee"])
        if r["direction"] == "buy":
            buy_shares += s
            buy_amount += a
            buy_fee += f
        else:
            sell_shares += s
            sell_amount += a
            sell_fee += f

    holding_shares = buy_shares - sell_shares
    total_cost = buy_amount + buy_fee
    avg_cost_nav = (
        (total_cost / buy_shares).quantize(Decimal("0.0001"))
        if buy_shares > 0
        else Decimal("0")
    )
    # Cost basis of the remaining position only (sold shares' cost is realized
    # and must not stay in the cost basis, or a sale shows up as a loss).
    remaining_cost = q2(holding_shares * avg_cost_nav)

    # Realized P&L: sell proceeds - cost of sold shares - sell fees
    realized_pnl = Decimal("0")
    if sell_shares > 0 and buy_shares > 0:
        realized_pnl = sell_amount - sell_shares * avg_cost_nav - sell_fee
    realized_pnl = q2(realized_pnl)

    unrealized_pnl = None
    total_pnl = None
    total_pnl_rate = None

    if current_nav and holding_shares > 0:
        nav_d = Decimal(current_nav)
        unrealized_pnl = q2(holding_shares * (nav_d - avg_cost_nav))
        total_pnl = q2(realized_pnl + unrealized_pnl)
        total_pnl_rate = (
            q2(total_pnl / total_cost * 100) if total_cost > 0 else Decimal("0")
        )
    elif current_nav and holding_shares == 0 and sell_shares > 0:
        unrealized_pnl = Decimal("0")
        total_pnl = realized_pnl
        total_pnl_rate = (
            q2(total_pnl / total_cost * 100) if total_cost > 0 else Decimal("0")
        )

    return {
        "holding_shares": str(holding_shares),
        "buy_shares": str(buy_shares),
        "sell_shares": str(sell_shares),
        "total_cost": str(total_cost),
        "remaining_cost": str(remaining_cost),
        "avg_cost_nav": str(avg_cost_nav),
        "sell_amount": str(sell_amount),
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
        "total_pnl": str(total_pnl) if total_pnl is not None else None,
        "total_pnl_rate": str(total_pnl_rate) if total_pnl_rate is not None else None,
        "current_nav": current_nav,
    }
