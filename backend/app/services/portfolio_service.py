"""Portfolio-level aggregation: summary, stock X-ray, and value history."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from ..core import CST
from ..fund_source import (
    fetch_fund_holdings,
    fetch_nav_history,
    fetch_realtime_estimate,
)
from ..repositories import positions_repo, tx_repo
from .holdings import compute_pnl
from .stock_industry_service import get_stock_industries

logger = logging.getLogger(__name__)


async def compute_summary(conn: sqlite3.Connection, pf_id: int) -> dict:
    """Aggregated portfolio stats: current value, cost, P&L, per-fund breakdown."""
    funds = positions_repo.list_holdings_with_shares(conn, pf_id)

    t0 = time.perf_counter()

    codes = [
        f["code"]
        for f in funds
        if f.get("holding_shares") and Decimal(f["holding_shares"]) > 0
    ]
    tx_rows_by_code = tx_repo.list_for_pnl_bulk(conn, pf_id, codes)
    pnl_map: dict[str, dict] = {
        code: compute_pnl(conn, pf_id, code, rows=tx_rows_by_code.get(code, []))
        for code in codes
    }

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


async def compute_holdings_xray(conn: sqlite3.Connection, pf_id: int) -> dict:
    """Stock-level X-ray: aggregate top-10 holdings across portfolio funds."""
    summary = await compute_summary(conn, pf_id)
    items: list[dict] = summary.get("items", [])

    active = [it for it in items if it.get("current_value")]

    async def _fetch(fund: dict) -> tuple[dict, list[dict]]:
        try:
            h = await fetch_fund_holdings(fund["code"])
        except Exception:
            h = []
        return fund, h

    pairs = await asyncio.gather(*[_fetch(f) for f in active])

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

    ind_map = await get_stock_industries(list(agg.keys()))

    sector_agg: dict[str, Decimal] = defaultdict(Decimal)
    for sc, v in agg.items():
        industry = ind_map.get(sc) or "未分类"
        sector_agg[industry] += v["exposure"]

    stocks = sorted(
        [
            {
                "stock_code": v["stock_code"],
                "stock_name": v["stock_name"],
                "industry": ind_map.get(v["stock_code"]),
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
        key=lambda x: float(x["exposure"]),  # type: ignore[arg-type]
        reverse=True,
    )

    # ponytail: cross-fund overlap is an intentional double-count in covered_value
    covered_value = sum((Decimal(str(s["exposure"])) for s in stocks), Decimal("0"))

    sectors = sorted(
        [
            {
                "name": name,
                "exposure": str(exp.quantize(Decimal("0.01"))),
                "weight_pct": (
                    round(float(exp / total_value * 100), 2) if total_value > 0 else 0.0
                ),
            }
            for name, exp in sector_agg.items()
        ],
        key=lambda x: float(x["exposure"]),  # type: ignore[arg-type]
        reverse=True,
    )

    return {
        "portfolio_id": pf_id,
        "total_value": str(total_value.quantize(Decimal("0.01"))),
        "covered_value": str(covered_value.quantize(Decimal("0.01"))),
        "stocks": stocks,
        "sectors": sectors,
        "coverage": coverage,
    }


async def compute_history(conn: sqlite3.Connection, pf_id: int, limit: int) -> dict:
    """Portfolio value history: holdings × NAV per date, plus today's estimate."""
    limit = max(1, min(limit, 365))

    transactions = tx_repo.list_for_portfolio(conn, pf_id)
    current_holdings = positions_repo.current_holdings(conn, pf_id)
    imported_funds = positions_repo.imported_amounts(conn, pf_id)

    tx_by_code: dict[str, list[dict]] = defaultdict(list)
    for tx in transactions:
        tx_by_code[tx["code"]].append(tx)

    tx_codes = list(tx_by_code.keys())
    imported_codes = list(imported_funds.keys())
    all_codes = list(set(tx_codes + imported_codes))

    if not all_codes:
        return {"portfolio_id": pf_id, "count": 0, "history": []}

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

    implied_shares: dict[str, Decimal] = {}
    excluded_codes: list[str] = []
    for code, holding_amount in imported_funds.items():
        nav_dict = nav_map.get(code, {})
        if nav_dict:
            latest_nav = nav_dict[max(nav_dict.keys())]
            if latest_nav > 0:
                implied_shares[code] = holding_amount / latest_nav
        else:
            excluded_codes.append(code)
            logger.warning(
                "portfolio_history(pf=%d): no NAV data for %s, excluded",
                pf_id,
                code,
            )

    all_dates = sorted({d for nd in nav_map.values() for d in nd})
    all_dates = all_dates[-limit:]

    date_totals: dict[str, Decimal] = {}
    for target_date in all_dates:
        total = Decimal("0")
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
        for code, imp_shares in implied_shares.items():
            nav = nav_map.get(code, {}).get(target_date)
            if nav is None:
                continue
            total += imp_shares * nav
        if total > 0:
            date_totals[target_date] = total

    today = datetime.now(CST).strftime("%Y-%m-%d")
    today_total = sum(
        (
            current_holdings[code] * gsz
            for code, gsz in gsz_map.items()
            if code in current_holdings
        ),
        Decimal("0"),
    )
    for code, imp_shares in implied_shares.items():
        gsz = gsz_map.get(code)
        if gsz:
            today_total += imp_shares * gsz
        else:
            today_total += imported_funds[code]
    if today_total > 0:
        date_totals.setdefault(today, today_total)

    sorted_items = sorted(date_totals.items())
    result: dict = {
        "portfolio_id": pf_id,
        "count": len(sorted_items),
        "history": [
            {"date": date, "total_value": float(value.quantize(Decimal("0.01")))}
            for date, value in sorted_items
        ],
    }
    if excluded_codes:
        result["excluded_codes"] = excluded_codes
    return result
