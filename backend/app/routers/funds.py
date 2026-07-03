"""Fund pool management, search, and per-fund data endpoints."""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core import is_valid_code, validate_code
from ..db import get_request_conn
from ..fund_source import (
    fetch_fund_detail,
    fetch_fund_holdings,
    fetch_fund_info,
    fetch_latest_nav,
    fetch_nav_history,
    fetch_nav_on_date,
    fetch_realtime_estimate,
    search_fund_by_name,
)
from ..repositories import (
    funds_repo,
    portfolios_repo,
    positions_repo,
    snapshot_repo,
    tx_repo,
)
from ..schemas import BatchFundItem, BatchFundsPayload
from ..services.holdings import recompute_holding_shares

logger = logging.getLogger(__name__)

router = APIRouter(tags=["funds"])


@router.get("/api/funds")
def list_funds(conn: sqlite3.Connection = Depends(get_request_conn)) -> dict:
    return {"items": funds_repo.list_funds(conn)}


@router.get("/api/funds/overview")
async def funds_overview(conn: sqlite3.Connection = Depends(get_request_conn)) -> dict:
    funds = funds_repo.list_funds(conn)
    codes = [f["code"] for f in funds]

    t0 = time.perf_counter()

    snapshot_map = snapshot_repo.latest_bulk(conn, codes)
    tx_count_map = tx_repo.count_bulk_for_codes(conn, codes)

    async def _fetch_one(f: dict) -> dict:
        code = f["code"]
        latest_snapshot = snapshot_map.get(code)

        if latest_snapshot is None:
            try:
                q = await fetch_realtime_estimate(code)
                latest_snapshot = {
                    "code": code,
                    "name": q.get("name"),
                    "gsz": q.get("gsz"),
                    "gszzl": q.get("gszzl"),
                    "gztime": q.get("gztime"),
                    "captured_at": None,
                }
            except Exception:
                latest_snapshot = None

        return {
            "fund": f,
            "latest": latest_snapshot,
            "has_transactions": tx_count_map.get(code, 0) > 0,
        }

    items = list(await asyncio.gather(*[_fetch_one(f) for f in funds]))
    logger.info(
        "funds_overview: %d funds fetched in %.3fs",
        len(funds),
        time.perf_counter() - t0,
    )
    return {"items": items}


@router.get("/api/funds/search")
async def search_funds(q: str = "") -> dict:
    """Search funds by name or code keyword via eastmoney."""
    q = q.strip()
    if not q:
        return {"results": []}
    if len(q) > 50:
        raise HTTPException(status_code=400, detail="搜索词过长（最多 50 个字符）")
    try:
        results = await search_fund_by_name(q, limit=20)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"基金搜索源（eastmoney）请求失败: {exc}"
        )
    return {"results": results}


@router.post("/api/funds/batch")
async def add_funds_batch(
    payload: BatchFundsPayload, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict:
    # ponytail: writes are interleaved with several awaited HTTP calls below,
    # so the request-scoped connection's write transaction stays open longer
    # than ideal. Single-user SQLite today has no concurrent writer to block;
    # split network resolution from the write phase if multi-user lands.
    now = datetime.now(timezone.utc).isoformat()

    # ── Resolve or create the target portfolio ────────────────────────────────
    if payload.portfolio_id is not None:
        if not portfolios_repo.exists(conn, payload.portfolio_id):
            raise HTTPException(status_code=404, detail="组合不存在")
        pf_id: int = payload.portfolio_id
    else:
        # Derive name: explicit > auto-date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pf_name = (payload.portfolio_name or "").strip() or f"导入 {today}"
        pf_id = portfolios_repo.create(conn, pf_name, now)

    # ── Resolve items: cross-check code and name when both are provided ───────
    resolved_items: list[BatchFundItem] = []
    unresolved: list[str] = []
    warnings: list[str] = []

    for item in payload.funds:
        has_code = bool(item.code and is_valid_code(item.code.strip()))
        has_name = bool(item.name and item.name.strip())

        if has_code and has_name:
            try:
                info = await fetch_fund_info(item.code.strip())  # type: ignore[union-attr]
                actual_name: str = info.get("name") or ""
                provided_name: str = item.name.strip()  # type: ignore[union-attr]
                if (
                    actual_name
                    and provided_name not in actual_name
                    and actual_name not in provided_name
                ):
                    warnings.append(
                        f"代码 {item.code} 对应名称为「{actual_name}」"
                        f"，与「{provided_name}」不一致，已按代码导入"
                    )
            except Exception:
                pass
            resolved_items.append(item)

        elif has_code:
            resolved_items.append(item)

        elif has_name:
            try:
                results = await search_fund_by_name(item.name.strip(), limit=1)  # type: ignore[union-attr]
                if results:
                    resolved_items.append(
                        item.model_copy(update={"code": results[0]["code"]})
                    )
                else:
                    unresolved.append(item.name)  # type: ignore[arg-type]
            except Exception:
                unresolved.append(item.name)  # type: ignore[arg-type]

        else:
            unresolved.append(str(item.code or item.name or "unknown"))

    extra: dict[str, BatchFundItem] = {
        item.code.strip(): item for item in resolved_items
    }  # type: ignore[union-attr]
    all_codes: list[str] = list(extra.keys())
    for c in payload.codes:
        c = c.strip()
        if c not in extra:
            all_codes.append(c)

    valid: list[str] = []
    invalid: list[str] = list(unresolved)
    for c in all_codes:
        if is_valid_code(c):
            valid.append(c)
        else:
            invalid.append(c)
    valid = sorted(set(valid))
    amounts = payload.amounts or {}

    # ── Fetch all fund infos in parallel ──────────────────────────────────────
    t_batch = time.perf_counter()

    async def _safe_fetch_info(code: str) -> tuple[str, str | None, str | None]:
        try:
            info = await fetch_fund_info(code)
            return code, info.get("name"), info.get("sector")
        except Exception:
            return code, None, None

    info_results = await asyncio.gather(*[_safe_fetch_info(c) for c in valid])
    fund_info_map: dict[str, tuple[str | None, str | None]] = {
        r[0]: (r[1], r[2]) for r in info_results
    }
    logger.info(
        "add_funds_batch(pf=%d): fetched info for %d codes in %.3fs",
        pf_id,
        len(valid),
        time.perf_counter() - t_batch,
    )

    actually_added: list[str] = []
    for code in valid:
        name, sector = fund_info_map.get(code, (None, None))
        item = extra.get(code)

        if not funds_repo.get_fund(conn, code) and not name:
            invalid.append(code)
            continue
        funds_repo.upsert_registry(conn, code, name, sector, now)

        amt = amounts.get(code)
        positions_repo.upsert(
            conn,
            pf_id,
            code,
            now,
            amount=float(amt) if amt is not None else None,
            imported_holding_amount=(
                float(item.holding_amount)
                if item and item.holding_amount is not None
                else None
            ),
            imported_cumulative_return=(
                float(item.cumulative_return)
                if item and item.cumulative_return is not None
                else None
            ),
            imported_holding_return=(
                float(item.holding_return)
                if item and item.holding_return is not None
                else None
            ),
        )
        actually_added.append(code)

    # ── Synthetic buy transaction for imported holding amounts ────────────────
    tx_now = datetime.now(timezone.utc).isoformat()
    nav_skipped: list[str] = []
    candidates: list[tuple[str, Decimal]] = []
    for code in actually_added:
        item = extra.get(code)
        if not item or item.holding_amount is None or item.holding_amount <= 0:
            continue
        if tx_repo.count_for_portfolio_code(conn, pf_id, code) > 0:
            nav_skipped.append(f"{code}（已有交易记录，跳过）")
            continue
        candidates.append((code, item.holding_amount))

    async def _safe_fetch_nav(code: str) -> tuple[str, dict | None, Exception | None]:
        try:
            return code, await fetch_latest_nav(code), None
        except Exception as e:
            return code, None, e

    nav_results = await asyncio.gather(
        *[_safe_fetch_nav(c) for c, _ in candidates]
    )
    holding_amounts = dict(candidates)

    for code, latest, err in nav_results:
        holding_amount = holding_amounts[code]
        if err is not None:
            nav_skipped.append(f"{code}（{err}）")
            continue
        if not latest or not latest.get("nav"):
            nav_skipped.append(f"{code}（无法获取净值）")
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(latest.get("date") or "")):
            nav_skipped.append(f"{code}（净值日期格式异常）")
            continue

        try:
            nav_val = Decimal(str(latest["nav"]))
            shares_val = (holding_amount / nav_val).quantize(Decimal("0.01"))
        except (InvalidOperation, ZeroDivisionError):
            nav_skipped.append(f"{code}（净值数据异常）")
            continue
        if shares_val <= 0:
            nav_skipped.append(f"{code}（计算份额为零）")
            continue

        # Recoverable checks are all above; nothing below should be caught and
        # silently swallowed as a "skip" once we've decided to write.
        amount_val = (nav_val * shares_val).quantize(Decimal("0.01"))
        tx_repo.insert(
            conn,
            code=code,
            portfolio_id=pf_id,
            direction="buy",
            trade_date=latest["date"],
            nav=str(nav_val),
            shares=str(shares_val),
            amount=str(amount_val),
            fee="0",
            source="import",
            created_at=tx_now,
        )
        recompute_holding_shares(conn, pf_id, code)

    if nav_skipped:
        warnings.extend(nav_skipped)

    return {
        "ok": True,
        "portfolio_id": pf_id,
        "added": actually_added,
        "invalid": invalid,
        "warnings": warnings,
    }


@router.post("/api/funds/{code}")
async def add_fund(
    code: str, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict:
    """Add a fund to the global registry (watchlist).

    Position data lives in /api/funds/batch.
    """
    code = validate_code(code)
    now = datetime.now(timezone.utc).isoformat()

    # Fetch fund info (name + sector) from data source
    name = None
    sector = None
    try:
        info = await fetch_fund_info(code)
        name = info.get("name")
        sector = info.get("sector")
    except Exception:
        pass

    existing = funds_repo.get_fund(conn, code)
    if existing:
        if sector and not funds_repo.has_sector(conn, code):
            funds_repo.upsert_registry(conn, code, name, sector, now)
    else:
        if name is None:
            raise HTTPException(
                status_code=400, detail="无法获取基金信息，请确认基金代码有效后重试"
            )
        funds_repo.upsert_registry(conn, code, name, sector, now)
    return {"ok": True, "code": code, "name": name, "sector": sector}


@router.delete("/api/funds/{code}")
def delete_fund(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    """Remove a fund from the watchlist."""
    code = validate_code(code)
    if not funds_repo.get_fund(conn, code):
        raise HTTPException(status_code=404, detail="fund not found")
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="portfolio not found")
        tx_repo.delete_scoped(conn, portfolio_id, code)
        positions_repo.delete_scoped(conn, portfolio_id, code)
        return {
            "ok": True,
            "code": code,
            "portfolio_id": portfolio_id,
            "scope": "portfolio",
        }
    snapshot_repo.delete_all_for_code(conn, code)
    tx_repo.delete_all_for_code(conn, code)
    positions_repo.delete_all_for_code(conn, code)
    funds_repo.delete(conn, code)
    return {"ok": True, "code": code, "scope": "global"}


@router.get("/api/funds/{code}/holdings")
async def get_fund_holdings(code: str) -> dict:
    code = validate_code(code)
    try:
        holdings = await fetch_fund_holdings(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "count": len(holdings), "holdings": holdings}


@router.get("/api/funds/{code}/detail")
async def get_fund_detail(code: str) -> dict:
    """Comprehensive fund detail: manager, size, period returns, asset allocation."""
    code = validate_code(code)
    try:
        detail = await fetch_fund_detail(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return detail


@router.get("/api/funds/{code}/nav-history")
async def get_nav_history(code: str, limit: int = 365) -> dict:
    """Historical NAV data for charting."""
    code = validate_code(code)
    limit = max(1, min(limit, 1000))
    try:
        history = await fetch_nav_history(code, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "count": len(history), "history": history}


@router.get("/api/funds/{code}/nav-on")
async def get_nav_on_date(code: str, date: str) -> dict:
    """Return the NAV for a specific date (YYYY-MM-DD)."""
    code = validate_code(code)
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date 必须是有效的 YYYY-MM-DD 日期")
    try:
        nav = await fetch_nav_on_date(code, date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "date": date, "nav": nav}
