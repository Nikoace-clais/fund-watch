"""Holding shares and P&L computation from the transaction log."""

from __future__ import annotations

from decimal import Decimal


def recompute_holding_shares(conn, code: str) -> None:
    """Recompute funds.holding_shares from transactions."""
    rows = conn.execute(
        "SELECT direction, shares FROM transactions WHERE code=?", (code,)
    ).fetchall()
    if not rows:
        conn.execute("UPDATE funds SET holding_shares=NULL WHERE code=?", (code,))
        return
    holding = Decimal("0")
    for r in rows:
        s = Decimal(r["shares"])
        if r["direction"] == "buy":
            holding += s
        else:
            holding -= s
    conn.execute(
        "UPDATE funds SET holding_shares=? WHERE code=?",
        (str(holding), code),
    )


def compute_pnl(conn, code: str, current_nav: str | None = None) -> dict:
    """Compute full P&L (realized + unrealized) for a fund."""
    rows = conn.execute(
        "SELECT direction, nav, shares, amount, fee FROM transactions"
        " WHERE code=? ORDER BY trade_date",
        (code,),
    ).fetchall()

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

    # Realized P&L: sell proceeds - cost of sold shares - sell fees
    # Guard: if buy_shares == 0 we have no cost basis; skip to avoid inflated P&L
    realized_pnl = Decimal("0")
    if sell_shares > 0 and buy_shares > 0:
        realized_pnl = sell_amount - sell_shares * avg_cost_nav - sell_fee
    realized_pnl = realized_pnl.quantize(Decimal("0.01"))

    # Unrealized P&L
    unrealized_pnl = None
    total_pnl = None
    total_pnl_rate = None

    if current_nav and holding_shares > 0:
        nav_d = Decimal(current_nav)
        unrealized_pnl = (holding_shares * (nav_d - avg_cost_nav)).quantize(
            Decimal("0.01")
        )
        total_pnl = (realized_pnl + unrealized_pnl).quantize(Decimal("0.01"))
        total_pnl_rate = (
            (total_pnl / total_cost * 100).quantize(Decimal("0.01"))
            if total_cost > 0
            else Decimal("0")
        )
    elif current_nav and holding_shares == 0 and sell_shares > 0:
        # All sold — only realized P&L
        unrealized_pnl = Decimal("0")
        total_pnl = realized_pnl
        total_pnl_rate = (
            (total_pnl / total_cost * 100).quantize(Decimal("0.01"))
            if total_cost > 0
            else Decimal("0")
        )

    return {
        "holding_shares": str(holding_shares),
        "buy_shares": str(buy_shares),
        "sell_shares": str(sell_shares),
        "total_cost": str(total_cost),
        "avg_cost_nav": str(avg_cost_nav),
        "sell_amount": str(sell_amount),
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
        "total_pnl": str(total_pnl) if total_pnl is not None else None,
        "total_pnl_rate": str(total_pnl_rate) if total_pnl_rate is not None else None,
        "current_nav": current_nav,
    }
