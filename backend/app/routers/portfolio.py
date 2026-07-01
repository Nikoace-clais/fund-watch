"""Portfolio aggregation: summary and value history."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_request_conn
from ..fund_source import (
    fetch_fund_holdings,
    fetch_nav_history,
    fetch_realtime_estimate,
    fetch_stock_industries,
)
from ..repositories import portfolios_repo, positions_repo, tx_repo
from ..services.portfolio_service import compute_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio"])


def _resolve_portfolio(conn: sqlite3.Connection, portfolio_id: int | None) -> int:
    """Return portfolio_id, defaulting to the first portfolio if none given."""
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="组合不存在")
        return portfolio_id
    first_id = portfolios_repo.first_id(conn)
    if first_id is None:
        raise HTTPException(status_code=404, detail="尚无组合，请先导入基金建立组合")
    return first_id


@router.get("/api/portfolio/summary")
async def portfolio_summary(
    portfolio_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    """Aggregated portfolio stats for a specific portfolio."""
    pf_id = _resolve_portfolio(conn, portfolio_id)
    return await compute_summary(conn, pf_id)


@router.get("/api/portfolio/holdings")
async def portfolio_holdings(
    portfolio_id: int | None = None,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    """Stock-level X-ray: aggregate top-10 holdings across portfolio funds."""
    pf_id = _resolve_portfolio(conn, portfolio_id)
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

    ind_map = await fetch_stock_industries(list(agg.keys()))

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


@router.get("/api/portfolio/history")
async def portfolio_history(
    portfolio_id: int | None = None,
    limit: int = 90,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    """Portfolio value history: holdings × NAV per date, plus today's estimate."""
    pf_id = _resolve_portfolio(conn, portfolio_id)
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
