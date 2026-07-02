"""Portfolio-level aggregation shared by the summary and holdings endpoints."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from decimal import Decimal

from ..fund_source import fetch_realtime_estimate
from ..repositories import positions_repo
from .holdings import compute_pnl

logger = logging.getLogger(__name__)


async def compute_summary(conn: sqlite3.Connection, pf_id: int) -> dict:
    """Aggregated portfolio stats: current value, cost, P&L, per-fund breakdown."""
    funds = positions_repo.list_holdings_with_shares(conn, pf_id)

    t0 = time.perf_counter()

    pnl_map: dict[str, dict] = {}
    codes = [
        f["code"]
        for f in funds
        if f.get("holding_shares") and Decimal(f["holding_shares"]) > 0
    ]
    for code in codes:
        pnl_map[code] = compute_pnl(conn, pf_id, code)

    async def _fetch_fund_item(f: dict) -> dict | None:
        code = f["code"]
        shares = Decimal(f["holding_shares"]) if f["holding_shares"] else Decimal("0")
        if shares <= 0:
            return None
        try:
            q = await fetch_realtime_estimate(code)
        except Exception:
            return None
        nav = Decimal(str(q.get("gsz", 0))) if q.get("gsz") else None
        if nav is None:
            return None
        daily_change = Decimal(str(q.get("gszzl"))) if q.get("gszzl") else Decimal("0")
        current_value = (shares * nav).quantize(Decimal("0.01"))
        daily_return_val = (current_value * daily_change / 100).quantize(
            Decimal("0.01")
        )
        pnl = pnl_map.get(code, {})
        cost = Decimal(pnl.get("total_cost", "0"))
        total_return = current_value - cost
        return_rate = (
            (total_return / cost * 100).quantize(Decimal("0.01"))
            if cost > 0
            else Decimal("0")
        )
        return {
            "code": code,
            "name": f["name"] or q.get("name"),
            "shares": str(shares),
            "nav": str(nav),
            "daily_change": float(daily_change),
            "current_value": str(current_value),
            "daily_return": str(daily_return_val),
            "total_cost": str(cost),
            "total_return": str(total_return.quantize(Decimal("0.01"))),
            "return_rate": str(return_rate),
            "_current_value_d": current_value,
            "_cost_d": cost,
            "_daily_return_d": daily_return_val,
        }

    results = await asyncio.gather(*[_fetch_fund_item(f) for f in funds])
    logger.info(
        "compute_summary(pf=%d): %d funds fetched in %.3fs",
        pf_id,
        len(funds),
        time.perf_counter() - t0,
    )

    items: list[dict] = []
    total_current = Decimal("0")
    total_cost = Decimal("0")
    total_current_with_cost = Decimal("0")
    total_daily_return = Decimal("0")

    for r in results:
        if r is None:
            continue
        cv = r.pop("_current_value_d")
        cost = r.pop("_cost_d")
        total_current += cv
        total_cost += cost
        total_current_with_cost += cv
        total_daily_return += r.pop("_daily_return_d")
        items.append(r)

    notx_funds = positions_repo.list_imported_positions(conn, pf_id)

    async def _fetch_notx(f: dict) -> dict:
        code = f["code"]
        amount = Decimal(str(f["holding_amount"]))
        daily_change = Decimal("0")
        daily_return_val = Decimal("0")
        try:
            q = await fetch_realtime_estimate(code)
            gszzl = q.get("gszzl")
            if gszzl is not None:
                daily_change = Decimal(str(gszzl))
                daily_return_val = (amount * daily_change / 100).quantize(
                    Decimal("0.01")
                )
        except Exception:
            pass
        cum_ret = f.get("imported_cumulative_return")
        hold_ret = f.get("imported_holding_return")
        return {
            "code": code,
            "name": f["name"],
            "shares": None,
            "nav": None,
            "daily_change": float(daily_change),
            "current_value": str(amount),
            "daily_return": str(daily_return_val),
            "total_cost": None,
            "total_return": str(Decimal(str(hold_ret or 0)).quantize(Decimal("0.01"))),
            "return_rate": None,
            "imported_cumulative_return": str(
                Decimal(str(cum_ret or 0)).quantize(Decimal("0.01"))
            ),
            "is_imported": True,
            "_amount_d": amount,
            "_daily_return_d": daily_return_val,
        }

    notx_results = list(await asyncio.gather(*[_fetch_notx(f) for f in notx_funds]))
    for r in notx_results:
        total_current += r.pop("_amount_d")
        total_daily_return += r.pop("_daily_return_d")
        items.append(r)

    total_return_rate = (
        ((total_current_with_cost - total_cost) / total_cost * 100).quantize(
            Decimal("0.01")
        )
        if total_cost > 0
        else Decimal("0")
    )

    watch_codes = positions_repo.list_watch_only_codes(conn, pf_id)

    # total_current includes imported (no-cost-basis) holdings' market value,
    # so total_current - total_cost would count that value as pure profit.
    # Sum each item's own displayed total_return instead — for tx-based
    # holdings that's current_value - cost; for imported ones it's the
    # user-supplied imported_holding_return.
    total_return_sum = sum((Decimal(it["total_return"]) for it in items), Decimal("0"))

    return {
        "portfolio_id": pf_id,
        "total_current": str(total_current),
        "total_cost": str(total_cost),
        "total_daily_return": str(total_daily_return),
        "total_return": str(total_return_sum.quantize(Decimal("0.01"))),
        "total_return_rate": str(total_return_rate),
        "fund_count": len(items),
        "items": items,
        "watch_codes": watch_codes,
    }
