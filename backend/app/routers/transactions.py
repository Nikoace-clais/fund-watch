"""Transaction log endpoints: CRUD, CSV import, and P&L."""

from __future__ import annotations

import csv
import io
import sqlite3
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..core import (
    is_valid_code,
    is_valid_date,
    q2,
    read_upload_limited,
    resolve_portfolio,
    safe_await,
    utc_now_iso,
    validate_code,
)
from ..db import get_request_conn
from ..fund_source import fetch_realtime_estimate
from ..repositories import funds_repo, positions_repo, tx_repo
from ..schemas import AddTransactionPayload
from ..services.holdings import (
    compute_pnl,
    never_negative_when_replayed,
    recompute_holding_shares,
)

router = APIRouter(tags=["transactions"])

_CSV_MAX_BYTES = 2 * 1024 * 1024  # CSV 导入上限 2MB


def _parse_tx_fields(
    direction: str, trade_date: str, nav: str, shares: str, fee: str
) -> tuple[Decimal, Decimal, Decimal, str]:
    """direction→日期→Decimal 解析→正数→amount 五步校验（手工录入/CSV 共用）。

    非法输入抛 ValueError（统一文案），由调用方翻译为自己的错误通道：
    手工录入 → 400，CSV 导入 → 该行的 errors 条目。
    返回 (nav_d, shares_d, fee_d, amount)。
    """
    if direction not in ("buy", "sell"):
        raise ValueError("direction must be 'buy' or 'sell'")
    if not is_valid_date(trade_date):
        raise ValueError("trade_date 必须是有效的 YYYY-MM-DD 日期")
    try:
        nav_d = Decimal(nav)
        shares_d = Decimal(shares)
        fee_d = Decimal(fee)
    except InvalidOperation as exc:
        raise ValueError("invalid numeric value for nav/shares/fee") from exc
    if nav_d <= 0 or shares_d <= 0 or fee_d < 0:
        raise ValueError("nav and shares must be positive, fee non-negative")
    return nav_d, shares_d, fee_d, str(q2(nav_d * shares_d))


def _sell_guard_extra(trade_date: str, shares_d: Decimal) -> list[dict[str, Any]]:
    """构造卖出回放守卫的 extra 行（待写入的这笔卖出）。"""
    return [{"direction": "sell", "trade_date": trade_date, "shares": str(shares_d)}]


def _decode_csv(raw: bytes) -> str:
    """Decode CSV bytes: 先试 UTF-8（含 BOM），失败回退 GB18030。

    国内 Excel 导出的 CSV 常见 GBK 编码；两种都解不了说明不是文本 CSV。
    """
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="无法识别文件编码，请使用 UTF-8 或 GBK 编码的 CSV 文件",
        ) from exc


@router.get("/api/funds/{code}/transactions")
def list_transactions(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    code = validate_code(code)
    pf_id = resolve_portfolio(conn, portfolio_id)
    items = tx_repo.list_by_code(conn, pf_id, code)
    return {"code": code, "portfolio_id": pf_id, "items": items}


@router.post("/api/funds/{code}/transactions")
def add_transaction(
    code: str,
    payload: AddTransactionPayload,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    code = validate_code(code)
    pf_id = resolve_portfolio(conn, payload.portfolio_id)

    try:
        nav_d, shares_d, fee_d, amount = _parse_tx_fields(
            payload.direction,
            payload.trade_date,
            payload.nav,
            payload.shares,
            payload.fee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    now = utc_now_iso()

    if not funds_repo.get_fund(conn, code):
        raise HTTPException(status_code=404, detail="fund not found")

    positions_repo.ensure_exists(conn, pf_id, code, now)

    if payload.direction == "sell" and not never_negative_when_replayed(
        conn, pf_id, code, extra=_sell_guard_extra(payload.trade_date, shares_d)
    ):
        raise HTTPException(status_code=400, detail="卖出日期的持仓份额不足")

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
) -> dict[str, Any]:
    row = tx_repo.get(conn, tx_id)
    if not row:
        raise HTTPException(status_code=404, detail="transaction not found")
    code = row["code"]
    pf_id = row["portfolio_id"]

    if pf_id is not None and not never_negative_when_replayed(
        conn, pf_id, code, remove_id=tx_id
    ):
        raise HTTPException(status_code=400, detail="删除失败：会导致持仓为负")

    tx_repo.delete(conn, tx_id)
    if pf_id is not None:
        recompute_holding_shares(conn, pf_id, code)
    return {"ok": True, "deleted": tx_id}


@router.get("/api/funds/{code}/pnl")
async def get_pnl(
    code: str,
    portfolio_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    code = validate_code(code)
    pf_id = resolve_portfolio(conn, portfolio_id)
    current_nav = None
    q = await safe_await(fetch_realtime_estimate(code))
    if q:
        # gsz 多为 float：先经 str() 再进 Decimal，避免二进制浮点尾差
        raw_gsz = q.get("gsz")
        current_nav = str(raw_gsz) if raw_gsz else None

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
) -> dict[str, Any]:
    pf_id = resolve_portfolio(conn, portfolio_id)
    raw = await read_upload_limited(file, _CSV_MAX_BYTES, "CSV 文件过大，上限 2MB")
    content = _decode_csv(raw)
    reader = csv.DictReader(io.StringIO(content))

    now = utc_now_iso()
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
            if not funds_repo.get_fund(conn, c):
                errors.append(f"line {i}: fund {c} not found")
                continue
            direction = row["direction"].strip()
            trade_date = row["trade_date"].strip()
            nav_d, shares_d, fee_d, amount = _parse_tx_fields(
                direction,
                trade_date,
                row["nav"].strip(),
                row["shares"].strip(),
                row.get("fee", "0").strip() or "0",
            )
            note = row.get("note", "").strip()

            if tx_repo.find_duplicate(
                conn, pf_id, c, direction, trade_date, str(nav_d), str(shares_d)
            ):
                skipped += 1
                continue

            # Replay the log by trade_date (rows inserted earlier in this CSV
            # are already visible via conn), so a sell dated before its buys
            # is rejected even when the overall net would stay positive.
            if direction == "sell" and not never_negative_when_replayed(
                conn, pf_id, c, extra=_sell_guard_extra(trade_date, shares_d)
            ):
                errors.append(f"line {i}: 该卖出日期的持仓份额不足")
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
        except (KeyError, InvalidOperation, ValueError) as e:
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
