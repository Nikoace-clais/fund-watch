"""Portfolio aggregation: summary and value history."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter

from ..db import get_conn
from ..fund_source import (
    fetch_fund_holdings,
    fetch_nav_history,
    fetch_realtime_estimate,
)
from ..services.holdings import compute_pnl

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio/summary")
async def portfolio_summary() -> dict:
    """Aggregated portfolio stats: total value, daily return, cumulative return."""
    with get_conn() as conn:
        funds = [
            dict(r)
            for r in conn.execute(
                "SELECT code, name, holding_shares FROM funds"
                " WHERE holding_shares IS NOT NULL ORDER BY created_at DESC"
            ).fetchall()
        ]

    t0 = time.perf_counter()

    # I2 fix: batch-compute PnL for all funds in ONE DB connection before async gather
    pnl_map: dict[str, dict] = {}
    codes = [
        f["code"]
        for f in funds
        if f.get("holding_shares") and Decimal(f["holding_shares"]) > 0
    ]
    if codes:
        with get_conn() as conn:
            for code in codes:
                pnl_map[code] = compute_pnl(conn, code)

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
        "portfolio_summary: %d funds fetched in %.3fs",
        len(funds),
        time.perf_counter() - t0,
    )

    items: list[dict] = []
    total_current = Decimal("0")
    total_cost = Decimal("0")
    total_current_with_cost = Decimal("0")  # tx-based funds only, for return rate
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

    # Funds with no transactions: COALESCE(imported_holding_amount, amount) as base,
    # fetch realtime gszzl to compute today's daily return.
    with get_conn() as conn:
        notx_funds = [
            dict(r)
            for r in conn.execute(
                """SELECT code, name,
                      COALESCE(imported_holding_amount, amount) AS holding_amount,
                      imported_cumulative_return,
                      imported_holding_return
               FROM funds
               WHERE holding_shares IS NULL
                 AND COALESCE(imported_holding_amount, amount) > 0
               ORDER BY created_at DESC"""
            ).fetchall()
        ]

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

    # I1 fix: rate uses only tx-based funds (those with known cost basis)
    total_return_rate = (
        ((total_current_with_cost - total_cost) / total_cost * 100).quantize(
            Decimal("0.01")
        )
        if total_cost > 0
        else Decimal("0")
    )

    return {
        "total_current": str(total_current),
        "total_cost": str(total_cost),
        "total_daily_return": str(total_daily_return),
        "total_return": str((total_current - total_cost).quantize(Decimal("0.01"))),
        "total_return_rate": str(total_return_rate),
        "fund_count": len(items),
        "items": items,
    }


@router.get("/api/portfolio/holdings")
async def portfolio_holdings() -> dict:
    """Stock-level X-ray: aggregate top-10 holdings across all portfolio funds.

    Returns exposure per stock (fund market-value × holding percentage),
    sorted descending. Stocks held by ≥2 funds are flagged via fund_count.
    """
    summary = await portfolio_summary()
    items: list[dict] = summary.get("items", [])

    # Only funds with a known current_value can contribute
    active = [it for it in items if it.get("current_value")]

    async def _fetch(fund: dict) -> tuple[dict, list[dict]]:
        try:
            h = await fetch_fund_holdings(fund["code"])
        except Exception:
            h = []
        return fund, h

    pairs = await asyncio.gather(*[_fetch(f) for f in active])

    # Aggregate: stock_code → {exposure, stock_name, funds[], coverage per fund}
    agg: dict[str, dict] = {}
    coverage: dict[str, float] = {}

    for fund, holdings in pairs:
        if not holdings:
            continue
        cv = Decimal(str(fund["current_value"]))
        fund_coverage = 0.0
        for h in holdings:
            pct = h.get("percentage")
            if pct is None:
                continue
            contribution = (cv * Decimal(str(pct)) / 100).quantize(Decimal("0.01"))
            sc = h["stock_code"]
            if sc not in agg:
                agg[sc] = {
                    "stock_code": sc,
                    "stock_name": h["stock_name"],
                    "exposure": Decimal("0"),
                    "funds": [],
                }
            agg[sc]["exposure"] += contribution
            agg[sc]["funds"].append(
                {
                    "code": fund["code"],
                    "name": fund.get("name") or fund["code"],
                    "percentage": float(pct),
                    "contribution": str(contribution),
                }
            )
            fund_coverage += float(pct)
        coverage[fund["code"]] = round(fund_coverage, 2)

    total_value = Decimal(str(summary.get("total_current", "0")))

    # Build sorted output
    stocks = sorted(
        [
            {
                "stock_code": v["stock_code"],
                "stock_name": v["stock_name"],
                "exposure": str(v["exposure"].quantize(Decimal("0.01"))),
                "weight_pct": (
                    round(float(v["exposure"] / total_value * 100), 2)
                    if total_value > 0
                    else 0.0
                ),
                "fund_count": len(v["funds"]),
                "funds": v["funds"],
            }
            for v in agg.values()
        ],
        key=lambda x: float(x["exposure"]),
        reverse=True,
    )

    # ponytail: cross-fund overlap is an intentional double-count in covered_value
    covered_value = sum((Decimal(s["exposure"]) for s in stocks), Decimal("0"))

    return {
        "total_value": str(total_value.quantize(Decimal("0.01"))),
        "covered_value": str(covered_value.quantize(Decimal("0.01"))),
        "stocks": stocks,
        "coverage": coverage,
    }


@router.get("/api/portfolio/history")
async def portfolio_history(limit: int = 90) -> dict:
    """Portfolio value history: holdings × NAV per date, plus today's estimate.

    Funds with transactions: per-date shares from transaction log × NAV.
    Imported funds without transactions: implied shares = holding_amount / latest_nav.
    """
    limit = max(1, min(limit, 365))

    with get_conn() as conn:
        transactions = [
            dict(r)
            for r in conn.execute(
                "SELECT code, direction, trade_date, shares"
                " FROM transactions ORDER BY trade_date ASC"
            ).fetchall()
        ]
        current_holdings = {
            r["code"]: Decimal(r["holding_shares"])
            for r in conn.execute(
                "SELECT code, holding_shares FROM funds"
                " WHERE holding_shares IS NOT NULL"
            ).fetchall()
            if r["holding_shares"] and Decimal(r["holding_shares"]) > 0
        }
        # Imported funds without any transactions: use holding_amount to infer shares
        imported_funds: dict[str, Decimal] = {
            r["code"]: Decimal(str(r["holding_amount"]))
            for r in conn.execute(
                "SELECT code,"
                " COALESCE(imported_holding_amount, amount) AS holding_amount"
                " FROM funds WHERE holding_shares IS NULL"
                " AND COALESCE(imported_holding_amount, amount) > 0"
            ).fetchall()
        }

    tx_by_code: dict[str, list[dict]] = defaultdict(list)
    for tx in transactions:
        tx_by_code[tx["code"]].append(tx)

    tx_codes = list(tx_by_code.keys())
    imported_codes = list(imported_funds.keys())
    all_codes = list(set(tx_codes + imported_codes))

    if not all_codes:
        return {"count": 0, "history": []}

    async def _fetch_code(code: str) -> tuple[str, dict[str, Decimal], Decimal | None]:
        nav_dict: dict[str, Decimal] = {}
        gsz: Decimal | None = None
        try:
            hist = await fetch_nav_history(code, limit=limit + 30)
            nav_dict = {
                h["date"]: Decimal(str(h["nav"]))
                for h in hist
                if h.get("date") and h.get("nav") is not None
            }
        except Exception:
            pass
        try:
            q = await fetch_realtime_estimate(code)
            raw = q.get("gsz")
            if raw:
                gsz = Decimal(str(raw))
        except Exception:
            pass
        return code, nav_dict, gsz

    fetch_results = await asyncio.gather(*[_fetch_code(c) for c in all_codes])

    nav_map: dict[str, dict[str, Decimal]] = {}
    gsz_map: dict[str, Decimal] = {}
    for code, nav_dict, gsz in fetch_results:
        nav_map[code] = nav_dict
        if gsz:
            gsz_map[code] = gsz

    # Implied shares for imported funds: holding_amount ÷ latest confirmed NAV
    implied_shares: dict[str, Decimal] = {}
    excluded_codes: list[str] = []
    for code, holding_amount in imported_funds.items():
        nav_dict = nav_map.get(code, {})
        if nav_dict:
            latest_nav = nav_dict[max(nav_dict.keys())]
            if latest_nav > 0:
                implied_shares[code] = holding_amount / latest_nav
        else:
            # I6 fix: log and collect codes excluded due to missing NAV data
            excluded_codes.append(code)
            logger.warning(
                "portfolio_history: no NAV data for %s, excluded from chart", code
            )

    all_dates = sorted({d for nd in nav_map.values() for d in nd})
    all_dates = all_dates[-limit:]

    date_totals: dict[str, Decimal] = {}
    for target_date in all_dates:
        total = Decimal("0")
        # Funds with transactions: per-date share count from transaction log
        for code in tx_codes:
            shares = Decimal("0")
            for tx in tx_by_code[code]:
                if tx["trade_date"] <= target_date:
                    if tx["direction"] == "buy":
                        shares += Decimal(tx["shares"])
                    else:
                        shares -= Decimal(tx["shares"])
            if shares <= 0:
                continue
            nav = nav_map.get(code, {}).get(target_date)
            if nav is None:
                continue
            total += shares * nav
        # Imported funds without transactions: implied shares × that day's NAV
        for code, imp_shares in implied_shares.items():
            nav = nav_map.get(code, {}).get(target_date)
            if nav is None:
                continue
            total += imp_shares * nav
        if total > 0:
            date_totals[target_date] = total

    # Use gsz for today's estimate; setdefault skips if confirmed NAV already present
    cst = timezone(timedelta(hours=8))
    today = datetime.now(cst).strftime("%Y-%m-%d")
    today_total = sum(
        (
            current_holdings[code] * gsz
            for code, gsz in gsz_map.items()
            if code in current_holdings
        ),
        Decimal("0"),
    )
    # C1 fix: use implied_shares × gsz (market value) not holding_amount (cost basis)
    for code, imp_shares in implied_shares.items():
        gsz = gsz_map.get(code)
        if gsz:
            today_total += imp_shares * gsz
        else:
            today_total += imported_funds[code]  # fallback to holding_amount
    # C2 fix: setdefault — don't overwrite an already-confirmed NAV for today
    if today_total > 0:
        date_totals.setdefault(today, today_total)

    sorted_items = sorted(date_totals.items())
    result: dict = {
        "count": len(sorted_items),
        "history": [
            {"date": date, "total_value": float(value.quantize(Decimal("0.01")))}
            for date, value in sorted_items
        ],
    }
    if excluded_codes:
        result["excluded_codes"] = (
            excluded_codes  # I6: surface missing-NAV funds to caller
        )
    return result
