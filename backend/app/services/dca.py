"""DCA plan performance statistics."""
from __future__ import annotations

import sqlite3
from decimal import Decimal

from fastapi import HTTPException


def calc_dca_stats(plan_id: int, conn: sqlite3.Connection) -> dict:
    """计算单个定投计划绩效"""
    plan = conn.execute("SELECT * FROM dca_plans WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")

    records = conn.execute(
        """SELECT r.status, t.shares, t.amount, t.nav
           FROM dca_records r
           LEFT JOIN transactions t ON t.id = r.transaction_id
           WHERE r.plan_id=?""",
        (plan_id,),
    ).fetchall()

    total_periods = len(records)
    success_count = sum(1 for r in records if r["status"] == "success")
    success_rows = [r for r in records if r["status"] == "success" and r["shares"]]
    failed_count = sum(1 for r in records if r["status"] == "failed")

    total_invested = sum((Decimal(r["amount"]) for r in success_rows), Decimal("0"))
    total_shares = sum((Decimal(r["shares"]) for r in success_rows), Decimal("0"))
    avg_cost = (total_invested / total_shares).quantize(Decimal("0.0001")) if total_shares else Decimal("0")

    # 最新净值：优先 fund_snapshots(gsz)，fallback transactions(nav)
    latest_nav_row = conn.execute(
        "SELECT gsz AS nav FROM fund_snapshots WHERE code=? AND gsz IS NOT NULL ORDER BY captured_at DESC LIMIT 1",
        (plan["code"],),
    ).fetchone()
    if not latest_nav_row:
        latest_nav_row = conn.execute(
            "SELECT nav FROM transactions WHERE code=? ORDER BY trade_date DESC LIMIT 1",
            (plan["code"],),
        ).fetchone()

    if latest_nav_row and total_shares:
        latest_nav = Decimal(str(latest_nav_row["nav"]))
        current_value = (total_shares * latest_nav).quantize(Decimal("0.01"))
        total_return = (current_value - total_invested).quantize(Decimal("0.01"))
        return_rate = (total_return / total_invested * 100).quantize(Decimal("0.01")) if total_invested else Decimal("0")
    else:
        current_value = total_invested
        total_return = Decimal("0")
        return_rate = Decimal("0")

    return {
        "plan_id": plan_id,
        "code": plan["code"],
        "total_periods": total_periods,
        "success_count": success_count,
        "failed_count": failed_count,
        "total_invested": str(total_invested.quantize(Decimal("0.01"))),
        "avg_cost": str(avg_cost),
        "total_shares": str(total_shares.quantize(Decimal("0.0001"))),
        "current_value": str(current_value),
        "total_return": str(total_return),
        "return_rate": str(return_rate),
    }
