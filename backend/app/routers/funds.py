"""Fund pool management, search, and per-fund data endpoints."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException

from ..core import validate_code
from ..db import get_conn
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
from ..schemas import (
    AddFundPayload,
    BatchFundItem,
    BatchFundsPayload,
    UpdateFundPayload,
)
from ..services.holdings import recompute_holding_shares

logger = logging.getLogger(__name__)

router = APIRouter(tags=["funds"])


@router.get("/api/funds")
def list_funds() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT code, name, sector, holding_shares, created_at"
            " FROM funds ORDER BY created_at DESC"
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/api/funds/overview")
async def funds_overview() -> dict:
    with get_conn() as conn:
        funds = [
            dict(r)
            for r in conn.execute(
                "SELECT code, name, sector, holding_shares, created_at"
                " FROM funds ORDER BY created_at DESC"
            ).fetchall()
        ]

    t0 = time.perf_counter()

    async def _fetch_one(f: dict) -> dict:
        code = f["code"]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT code,name,gsz,gszzl,gztime,captured_at"
                " FROM fund_snapshots WHERE code=? ORDER BY id DESC LIMIT 1",
                (code,),
            ).fetchone()
            tx_count = conn.execute(
                "SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)
            ).fetchone()["c"]

        latest_snapshot = dict(row) if row else None

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

        return {"fund": f, "latest": latest_snapshot, "has_transactions": tx_count > 0}

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
async def add_funds_batch(payload: BatchFundsPayload) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # ── Resolve or create the target portfolio ────────────────────────────────
    with get_conn() as conn:
        if payload.portfolio_id is not None:
            if not conn.execute(
                "SELECT 1 FROM portfolios WHERE id=?", (payload.portfolio_id,)
            ).fetchone():
                raise HTTPException(status_code=404, detail="组合不存在")
            pf_id: int = payload.portfolio_id
        else:
            # Derive name: explicit > auto-date
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            pf_name = (payload.portfolio_name or "").strip() or f"导入 {today}"
            cur = conn.execute(
                "INSERT INTO portfolios(name, created_at) VALUES(?, ?)",
                (pf_name, now),
            )
            pf_id = cur.lastrowid  # type: ignore[assignment]
        conn.commit()

    # ── Resolve items: cross-check code and name when both are provided ───────
    resolved_items: list[BatchFundItem] = []
    unresolved: list[str] = []
    warnings: list[str] = []

    for item in payload.funds:
        has_code = bool(item.code and re.match(r"^\d{6}$", item.code.strip()))
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
        if c.isdigit() and len(c) == 6:
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
    with get_conn() as conn:
        for code in valid:
            name, sector = fund_info_map.get(code, (None, None))
            item = extra.get(code)

            # ── Global fund registry (name/sector only) ──
            existing_fund = conn.execute(
                "SELECT code FROM funds WHERE code=?", (code,)
            ).fetchone()
            if not existing_fund and not name:
                invalid.append(code)
                continue
            if not existing_fund:
                conn.execute(
                    "INSERT INTO funds(code, name, sector, created_at) VALUES(?,?,?,?)",
                    (code, name, sector, now),
                )
            elif name or sector:
                updates, params_u = [], []
                if name:
                    updates.append("name=?")
                    params_u.append(name)
                if sector:
                    updates.append("sector=?")
                    params_u.append(sector)
                params_u.append(code)
                conn.execute(
                    f"UPDATE funds SET {','.join(updates)} WHERE code=?",
                    params_u,
                )

            # ── Portfolio-scoped position (upsert) ──
            amt = amounts.get(code)
            existing_pos = conn.execute(
                "SELECT id FROM positions WHERE portfolio_id=? AND code=?",
                (pf_id, code),
            ).fetchone()
            if existing_pos:
                pos_updates, pos_params = [], []
                if amt is not None:
                    pos_updates.append("amount=?")
                    pos_params.append(float(amt))
                if item:
                    if item.holding_amount is not None:
                        pos_updates.append("imported_holding_amount=?")
                        pos_params.append(float(item.holding_amount))
                    if item.cumulative_return is not None:
                        pos_updates.append("imported_cumulative_return=?")
                        pos_params.append(float(item.cumulative_return))
                    if item.holding_return is not None:
                        pos_updates.append("imported_holding_return=?")
                        pos_params.append(float(item.holding_return))
                if pos_updates:
                    pos_params += [pf_id, code]
                    conn.execute(
                        f"UPDATE positions SET {','.join(pos_updates)}"
                        " WHERE portfolio_id=? AND code=?",
                        pos_params,
                    )
            else:
                conn.execute(
                    """INSERT INTO positions
                       (portfolio_id,code,amount,imported_holding_amount,
                        imported_cumulative_return,imported_holding_return,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (
                        pf_id,
                        code,
                        float(amt) if amt is not None else None,
                        float(item.holding_amount)
                        if item and item.holding_amount is not None
                        else None,
                        float(item.cumulative_return)
                        if item and item.cumulative_return is not None
                        else None,
                        float(item.holding_return)
                        if item and item.holding_return is not None
                        else None,
                        now,
                    ),
                )
            actually_added.append(code)
        conn.commit()

    # ── Synthetic buy transaction for imported holding amounts ────────────────
    tx_now = datetime.now(timezone.utc).isoformat()
    nav_skipped: list[str] = []
    for code in actually_added:
        item = extra.get(code)
        if not item or item.holding_amount is None or item.holding_amount <= 0:
            continue
        try:
            with get_conn() as conn:
                existing_tx = conn.execute(
                    "SELECT COUNT(*) as c FROM transactions"
                    " WHERE portfolio_id=? AND code=?",
                    (pf_id, code),
                ).fetchone()["c"]
            if existing_tx > 0:
                nav_skipped.append(f"{code}（已有交易记录，跳过）")
                continue

            latest = await fetch_latest_nav(code)
            if not latest or not latest.get("nav"):
                nav_skipped.append(f"{code}（无法获取净值）")
                continue

            nav_val = Decimal(str(latest["nav"]))
            shares_val = (item.holding_amount / nav_val).quantize(Decimal("0.01"))
            if shares_val <= 0:
                nav_skipped.append(f"{code}（计算份额为零）")
                continue

            amount_val = (nav_val * shares_val).quantize(Decimal("0.01"))
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO transactions"
                    "(code,portfolio_id,direction,trade_date,nav,shares,amount,fee,source,created_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        code,
                        pf_id,
                        "buy",
                        latest["date"],
                        str(nav_val),
                        str(shares_val),
                        str(amount_val),
                        "0",
                        "import",
                        tx_now,
                    ),
                )
                recompute_holding_shares(conn, pf_id, code)
                conn.commit()
        except Exception as e:
            nav_skipped.append(f"{code}（{e}）")

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
async def add_fund(code: str, payload: AddFundPayload | None = None) -> dict:
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

    amount = float(payload.amount) if payload and payload.amount is not None else None

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT code FROM funds WHERE code=?", (code,)
        ).fetchone()
        if existing:
            if amount is not None:
                conn.execute("UPDATE funds SET amount=? WHERE code=?", (amount, code))
            if (
                sector
                and not conn.execute(
                    "SELECT sector FROM funds WHERE code=? AND sector IS NOT NULL",
                    (code,),
                ).fetchone()
            ):
                conn.execute(
                    "UPDATE funds SET sector=?, name=? WHERE code=?",
                    (sector, name, code),
                )
        else:
            if name is None:
                raise HTTPException(
                    status_code=400, detail="无法获取基金信息，请确认基金代码有效后重试"
                )
            conn.execute(
                "INSERT INTO funds(code,name,sector,amount,created_at)"
                " VALUES(?,?,?,?,?)",
                (code, name, sector, amount, now),
            )
        conn.commit()
    return {"ok": True, "code": code, "name": name, "sector": sector}


@router.patch("/api/funds/{code}")
def update_fund(code: str, payload: UpdateFundPayload) -> dict:
    code = validate_code(code)
    with get_conn() as conn:
        if not conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone():
            raise HTTPException(status_code=404, detail="fund not found")

        # If has transactions, reject manual shares edit
        if payload.holding_shares is not None:
            tx_count = conn.execute(
                "SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)
            ).fetchone()["c"]
            if tx_count > 0:
                raise HTTPException(
                    status_code=400, detail="有交易记录时不可手动编辑份额"
                )
            try:
                shares_d = Decimal(payload.holding_shares)
            except InvalidOperation:
                raise HTTPException(status_code=400, detail="无效的份额数值")
            if shares_d < 0:
                raise HTTPException(status_code=400, detail="份额不能为负数")

        updates = []
        params: list = []
        if payload.holding_shares is not None:
            updates.append("holding_shares=?")
            params.append(payload.holding_shares)
        if payload.sector is not None:
            updates.append("sector=?")
            params.append(payload.sector)
        if not updates:
            raise HTTPException(status_code=400, detail="nothing to update")
        params.append(code)
        conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
        conn.commit()
    return {"ok": True, "code": code}


@router.delete("/api/funds/{code}")
def delete_fund(code: str) -> dict:
    """Remove a fund from the watchlist."""
    code = validate_code(code)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT code FROM funds WHERE code=?", (code,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="fund not found")
        conn.execute("DELETE FROM fund_snapshots WHERE code=?", (code,))
        conn.execute("DELETE FROM transactions WHERE code=?", (code,))
        conn.execute("DELETE FROM funds WHERE code=?", (code,))
        conn.commit()
    return {"ok": True, "code": code}


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
