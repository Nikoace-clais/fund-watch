"""Transaction log endpoints: CRUD, CSV import, and P&L."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..core import validate_code
from ..db import get_conn
from ..fund_source import fetch_realtime_estimate
from ..schemas import AddTransactionPayload
from ..services.holdings import compute_pnl, recompute_holding_shares

router = APIRouter(tags=["transactions"])


@router.get("/api/funds/{code}/transactions")
def list_transactions(code: str) -> dict:
    code = validate_code(code)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE code=? ORDER BY trade_date DESC, id DESC",
            (code,),
        ).fetchall()
    return {"code": code, "items": [dict(r) for r in rows]}


@router.post("/api/funds/{code}/transactions")
def add_transaction(code: str, payload: AddTransactionPayload) -> dict:
    code = validate_code(code)
    if payload.direction not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="direction must be 'buy' or 'sell'")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", payload.trade_date):
        raise HTTPException(status_code=400, detail="trade_date must be YYYY-MM-DD")

    try:
        nav_d = Decimal(payload.nav)
        shares_d = Decimal(payload.shares)
        fee_d = Decimal(payload.fee)
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="invalid numeric value for nav/shares/fee")

    if nav_d <= 0 or shares_d <= 0 or fee_d < 0:
        raise HTTPException(status_code=400, detail="nav and shares must be positive, fee non-negative")

    amount = str((nav_d * shares_d).quantize(Decimal("0.01")))
    now = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        # Verify fund exists
        if not conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone():
            raise HTTPException(status_code=404, detail="fund not found")

        if payload.direction == "sell":
            # Check sufficient shares using Decimal for precision
            tx_rows = conn.execute(
                "SELECT direction, shares FROM transactions WHERE code=?", (code,)
            ).fetchall()
            current_holding = sum(
                Decimal(r["shares"]) if r["direction"] == "buy" else -Decimal(r["shares"])
                for r in tx_rows
            ) if tx_rows else Decimal("0")
            if shares_d > current_holding:
                raise HTTPException(status_code=400, detail="insufficient shares to sell")

        conn.execute(
            """INSERT INTO transactions(code,direction,trade_date,nav,shares,amount,fee,note,source,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (code, payload.direction, payload.trade_date, payload.nav, payload.shares, amount, payload.fee, payload.note, payload.source, now),
        )
        recompute_holding_shares(conn, code)
        conn.commit()

    return {"ok": True, "code": code}


@router.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT code, direction, shares FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="transaction not found")
        code = row["code"]

        # Simulate post-delete shares using Decimal for precision
        if row["direction"] == "buy":
            tx_rows = conn.execute(
                "SELECT direction, shares FROM transactions WHERE code=?", (code,)
            ).fetchall()
            current_holding = sum(
                Decimal(r["shares"]) if r["direction"] == "buy" else -Decimal(r["shares"])
                for r in tx_rows
            ) if tx_rows else Decimal("0")
            after_shares = current_holding - Decimal(row["shares"])
            if after_shares < 0:
                raise HTTPException(status_code=400, detail="删除失败：会导致持有份额为负")

        conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        recompute_holding_shares(conn, code)
        conn.commit()
    return {"ok": True, "deleted": tx_id}


@router.get("/api/funds/{code}/pnl")
async def get_pnl(code: str) -> dict:
    code = validate_code(code)
    # Try to get current NAV estimate
    current_nav = None
    try:
        q = await fetch_realtime_estimate(code)
        current_nav = q.get("gsz")
    except Exception:
        pass

    with get_conn() as conn:
        tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)).fetchone()["c"]
        if tx_count == 0:
            return {"code": code, "has_transactions": False}
        pnl = compute_pnl(conn, code, current_nav)

    return {"code": code, "has_transactions": True, **pnl}


@router.post("/api/transactions/csv")
async def import_csv(file: UploadFile = File(...)) -> dict:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0
    errors: list[str] = []
    affected_codes: set[str] = set()

    with get_conn() as conn:
        for i, row in enumerate(reader, start=2):  # line 1 is header
            try:
                c = row["code"].strip()
                if not (c.isdigit() and len(c) == 6):
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

                # Dedup check
                dup = conn.execute(
                    """SELECT id FROM transactions
                       WHERE code=? AND direction=? AND trade_date=? AND nav=? AND shares=?""",
                    (c, direction, row["trade_date"].strip(), str(nav_d), str(shares_d)),
                ).fetchone()
                if dup:
                    skipped += 1
                    continue

                conn.execute(
                    """INSERT INTO transactions(code,direction,trade_date,nav,shares,amount,fee,note,source,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (c, direction, row["trade_date"].strip(), str(nav_d), str(shares_d), amount, str(fee_d), note or None, "csv", now),
                )
                affected_codes.add(c)
                imported += 1
            except (KeyError, InvalidOperation) as e:
                errors.append(f"line {i}: {e}")

        for c in affected_codes:
            recompute_holding_shares(conn, c)
        conn.commit()

    return {"ok": True, "imported": imported, "skipped": skipped, "errors": errors}
