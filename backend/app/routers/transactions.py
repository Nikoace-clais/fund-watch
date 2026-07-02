"""Transaction log endpoints: CRUD, CSV import, and P&L."""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..core import is_valid_code, validate_code
from ..db import get_request_conn
from ..fund_source import fetch_realtime_estimate
from ..repositories import funds_repo, portfolios_repo, positions_repo, tx_repo
from ..schemas import AddTransactionPayload
from ..services.holdings import (
    compute_pnl,
    current_holding_shares,
    recompute_holding_shares,
)

router = APIRouter(tags=["transactions"])


def _resolve_tx_portfolio(conn: sqlite3.Connection, portfolio_id: int | None) -> int:
    """Return the portfolio_id, defaulting to the first existing portfolio.

    Raises 404 when no portfolio exists — create one via POST /api/portfolios first.
    """
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="组合不存在")
        return portfolio_id
    first_id = portfolios_repo.first_id(conn)
    if first_id is None:
        raise HTTPException(status_code=404, detail="尚无组合，请先导入基金建立组合")
    return first_id


@router.get("/api/funds/{code}/transactions")
def list_transactions(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    code = validate_code(code)
    pf_id = _resolve_tx_portfolio(conn, portfolio_id)
    items = tx_repo.list_by_code(conn, pf_id, code)
    return {"code": code, "portfolio_id": pf_id, "items": items}


@router.post("/api/funds/{code}/transactions")
def add_transaction(
    code: str,
    payload: AddTransactionPayload,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    code = validate_code(code)
    pf_id = _resolve_tx_portfolio(conn, payload.portfolio_id)

    if payload.direction not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="direction must be 'buy' or 'sell'")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", payload.trade_date):
        raise HTTPException(status_code=400, detail="trade_date must be YYYY-MM-DD")
    try:
        datetime.strptime(payload.trade_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="trade_date 不是有效日期")

    try:
        nav_d = Decimal(payload.nav)
        shares_d = Decimal(payload.shares)
        fee_d = Decimal(payload.fee)
    except InvalidOperation:
        raise HTTPException(
            status_code=400, detail="invalid numeric value for nav/shares/fee"
        )

    if nav_d <= 0 or shares_d <= 0 or fee_d < 0:
        raise HTTPException(
            status_code=400, detail="nav and shares must be positive, fee non-negative"
        )

    amount = str((nav_d * shares_d).quantize(Decimal("0.01")))
    now = datetime.now(timezone.utc).isoformat()

    if not funds_repo.get_fund(conn, code):
        raise HTTPException(status_code=404, detail="fund not found")

    positions_repo.ensure_exists(conn, pf_id, code, now)

    if payload.direction == "sell":
        current_holding = current_holding_shares(conn, pf_id, code)
        if shares_d > current_holding:
            raise HTTPException(status_code=400, detail="insufficient shares to sell")

    tx_repo.insert(
        conn,
        code=code,
        portfolio_id=pf_id,
        direction=payload.direction,
        trade_date=payload.trade_date,
        nav=payload.nav,
        shares=payload.shares,
        amount=amount,
        fee=payload.fee,
        note=payload.note,
        source=payload.source,
        created_at=now,
    )
    recompute_holding_shares(conn, pf_id, code)

    return {"ok": True, "code": code, "portfolio_id": pf_id}


@router.delete("/api/transactions/{tx_id}")
def delete_transaction(
    tx_id: int, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict:
    row = tx_repo.get(conn, tx_id)
    if not row:
        raise HTTPException(status_code=404, detail="transaction not found")
    code = row["code"]
    pf_id = row["portfolio_id"]

    if row["direction"] == "buy":
        current_holding = current_holding_shares(conn, pf_id, code)
        after_shares = current_holding - Decimal(row["shares"])
        if after_shares < 0:
            raise HTTPException(status_code=400, detail="删除失败：会导致持有份额为负")

    tx_repo.delete(conn, tx_id)
    if pf_id is not None:
        recompute_holding_shares(conn, pf_id, code)
    return {"ok": True, "deleted": tx_id}


@router.get("/api/funds/{code}/pnl")
async def get_pnl(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    code = validate_code(code)
    pf_id = _resolve_tx_portfolio(conn, portfolio_id)
    current_nav = None
    try:
        q = await fetch_realtime_estimate(code)
        current_nav = q.get("gsz")
    except Exception:
        pass

    tx_count = tx_repo.count_for_portfolio_code(conn, pf_id, code)
    if tx_count == 0:
        return {"code": code, "portfolio_id": pf_id, "has_transactions": False}
    pnl = compute_pnl(conn, pf_id, code, current_nav)

    return {"code": code, "portfolio_id": pf_id, "has_transactions": True, **pnl}


@router.post("/api/transactions/csv")
async def import_csv(
    file: UploadFile = File(...),
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict:
    pf_id = _resolve_tx_portfolio(conn, portfolio_id)
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0
    errors: list[str] = []
    affected_codes: set[str] = set()

    for i, row in enumerate(reader, start=2):
        try:
            c = row["code"].strip()
            if not is_valid_code(c):
                errors.append(f"line {i}: invalid code '{c}'")
                continue
            direction = row["direction"].strip()
            if direction not in ("buy", "sell"):
                errors.append(f"line {i}: invalid direction '{direction}'")
                continue
            nav_d = Decimal(row["nav"].strip())
            shares_d = Decimal(row["shares"].strip())
            fee_d = Decimal(row.get("fee", "0").strip() or "0")
            amount = str((nav_d * shares_d).quantize(Decimal("0.01")))
            note = row.get("note", "").strip()
            trade_date = row["trade_date"].strip()

            if tx_repo.find_duplicate(
                conn, pf_id, c, direction, trade_date, str(nav_d), str(shares_d)
            ):
                skipped += 1
                continue

            positions_repo.ensure_exists(conn, pf_id, c, now)

            tx_repo.insert(
                conn,
                code=c,
                portfolio_id=pf_id,
                direction=direction,
                trade_date=trade_date,
                nav=str(nav_d),
                shares=str(shares_d),
                amount=amount,
                fee=str(fee_d),
                note=note or None,
                source="csv",
                created_at=now,
            )
            affected_codes.add(c)
            imported += 1
        except (KeyError, InvalidOperation) as e:
            errors.append(f"line {i}: {e}")

    for c in affected_codes:
        recompute_holding_shares(conn, pf_id, c)

    return {
        "ok": True,
        "portfolio_id": pf_id,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }
