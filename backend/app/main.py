from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import get_conn, init_db, prune_old_snapshots
from .fund_source import (
    close_shared_client,
    fetch_fund_detail,
    fetch_fund_holdings,
    fetch_fund_info,
    fetch_latest_nav,
    fetch_market_indices,
    fetch_nav_history,
    fetch_nav_on_date,
    fetch_realtime_estimate,
    search_fund_by_name,
)
from .ocr_service import extract_fund_codes_from_image, extract_fund_names_from_text, extract_funds_with_amounts, extract_transaction_from_image

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
# Show DEBUG logs from fund_source so per-request timings are visible
logging.getLogger("app.fund_source").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

_CST = timezone(timedelta(hours=8))

# ── Cron state ────────────────────────────────────────────────────────────────
_cron_state: dict = {
    "last_pull_at": None,
    "pull_count": 0,
    "last_error": None,
    "is_active": False,
}


def _in_trading_hours() -> bool:
    """True when current CST time is within A-share trading windows (weekdays)."""
    now = datetime.now(_CST)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    t = now.hour * 60 + now.minute
    morning   = 9 * 60 + 25 <= t <= 11 * 60 + 35
    afternoon = 12 * 60 + 55 <= t <= 15 * 60 + 5
    return morning or afternoon


async def _snapshot_scheduler() -> None:
    """Background loop: pull snapshots every 5 min during trading hours.
    Also prunes snapshots older than 30 days once per day at startup and at midnight.
    """
    await asyncio.sleep(15)          # startup buffer
    logger.info("cron: scheduler started (interval=5min, trading-hours only)")
    last_prune_day: int = -1
    while True:
        now_cst = datetime.now(_CST)
        # I3 fix: prune old snapshots once per calendar day
        if now_cst.day != last_prune_day:
            try:
                deleted = prune_old_snapshots(keep_days=30)
                logger.info("cron: pruned %d old snapshots (keep_days=30)", deleted)
            except Exception as exc:
                logger.warning("cron: prune failed — %s", exc)
            last_prune_day = now_cst.day

        in_hours = _in_trading_hours()
        _cron_state["is_active"] = in_hours
        if in_hours:
            try:
                result = await pull_snapshots()
                _cron_state["last_pull_at"] = datetime.now(timezone.utc).isoformat()
                _cron_state["pull_count"] += 1
                _cron_state["last_error"] = None
                logger.info("cron: pull done — inserted=%s, total=%d",
                            result.get("inserted"), _cron_state["pull_count"])
            except Exception as exc:
                _cron_state["last_error"] = str(exc)
                logger.error("cron: pull failed — %s", exc)
        await asyncio.sleep(5 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_snapshot_scheduler())
    logger.info("Fund Watch API started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_shared_client()
    logger.info("Fund Watch API shutdown")


app = FastAPI(title="Fund Watch API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - t0
    level = logging.WARNING if elapsed > 3.0 else logging.INFO
    logger.log(level, "%s %s -> %d  %.3fs", request.method, request.url.path, response.status_code, elapsed)
    return response


class AddFundPayload(BaseModel):
    amount: float | None = None


class BatchFundItem(BaseModel):
    code: str | None = None
    name: str | None = None
    holding_amount: float | None = None
    cumulative_return: float | None = None
    holding_return: float | None = None

class BatchFundsPayload(BaseModel):
    codes: list[str] = []
    amounts: dict[str, float] | None = None
    funds: list[BatchFundItem] = []


class UpdateFundPayload(BaseModel):
    holding_shares: str | None = None
    sector: str | None = None


class AddTransactionPayload(BaseModel):
    direction: str  # 'buy' or 'sell'
    trade_date: str
    nav: str
    shares: str
    fee: str = "0"
    note: str | None = None
    source: str = "manual"




@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/funds")
def list_funds() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT code, name, sector, holding_shares, created_at FROM funds ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows]}


def _validate_code(code: str) -> str:
    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code


def _recompute_holding_shares(conn, code: str) -> None:
    """Recompute funds.holding_shares from transactions."""
    rows = conn.execute(
        "SELECT direction, shares FROM transactions WHERE code=?", (code,)
    ).fetchall()
    if not rows:
        conn.execute("UPDATE funds SET holding_shares=NULL WHERE code=?", (code,))
        return
    holding = Decimal("0")
    for r in rows:
        s = Decimal(r["shares"])
        if r["direction"] == "buy":
            holding += s
        else:
            holding -= s
    conn.execute(
        "UPDATE funds SET holding_shares=? WHERE code=?",
        (str(holding), code),
    )


def _compute_pnl(conn, code: str, current_nav: str | None = None) -> dict:
    """Compute full P&L (realized + unrealized) for a fund."""
    rows = conn.execute(
        "SELECT direction, nav, shares, amount, fee FROM transactions WHERE code=? ORDER BY trade_date",
        (code,),
    ).fetchall()

    buy_shares = Decimal("0")
    buy_amount = Decimal("0")
    buy_fee = Decimal("0")
    sell_shares = Decimal("0")
    sell_amount = Decimal("0")
    sell_fee = Decimal("0")

    for r in rows:
        s = Decimal(r["shares"])
        a = Decimal(r["amount"])
        f = Decimal(r["fee"])
        if r["direction"] == "buy":
            buy_shares += s
            buy_amount += a
            buy_fee += f
        else:
            sell_shares += s
            sell_amount += a
            sell_fee += f

    holding_shares = buy_shares - sell_shares
    total_cost = buy_amount + buy_fee
    avg_cost_nav = (total_cost / buy_shares).quantize(Decimal("0.0001")) if buy_shares > 0 else Decimal("0")

    # Realized P&L: sell proceeds - cost of sold shares - sell fees
    # Guard: if buy_shares == 0 we have no cost basis; skip to avoid inflated P&L
    realized_pnl = Decimal("0")
    if sell_shares > 0 and buy_shares > 0:
        realized_pnl = sell_amount - sell_shares * avg_cost_nav - sell_fee
    realized_pnl = realized_pnl.quantize(Decimal("0.01"))

    # Unrealized P&L
    unrealized_pnl = None
    total_pnl = None
    total_pnl_rate = None

    if current_nav and holding_shares > 0:
        nav_d = Decimal(current_nav)
        unrealized_pnl = (holding_shares * (nav_d - avg_cost_nav)).quantize(Decimal("0.01"))
        total_pnl = (realized_pnl + unrealized_pnl).quantize(Decimal("0.01"))
        total_pnl_rate = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")
    elif current_nav and holding_shares == 0 and sell_shares > 0:
        # All sold — only realized P&L
        unrealized_pnl = Decimal("0")
        total_pnl = realized_pnl
        total_pnl_rate = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    return {
        "holding_shares": str(holding_shares),
        "buy_shares": str(buy_shares),
        "sell_shares": str(sell_shares),
        "total_cost": str(total_cost),
        "avg_cost_nav": str(avg_cost_nav),
        "sell_amount": str(sell_amount),
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
        "total_pnl": str(total_pnl) if total_pnl is not None else None,
        "total_pnl_rate": str(total_pnl_rate) if total_pnl_rate is not None else None,
        "current_nav": current_nav,
    }


@app.post("/api/funds/recalc-percentage")
def recalc_percentage() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT code, amount FROM funds").fetchall()
        total = sum(r["amount"] for r in rows if r["amount"])
        if total > 0:
            for r in rows:
                pct = round((r["amount"] / total) * 100, 2) if r["amount"] else None
                conn.execute("UPDATE funds SET percentage=? WHERE code=?", (pct, r["code"]))
        conn.commit()
    return {"ok": True, "total": total}


@app.post("/api/funds/batch")
async def add_funds_batch(payload: BatchFundsPayload) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # Resolve items: cross-check code and name when both are provided
    resolved_items: list[BatchFundItem] = []
    unresolved: list[str] = []
    warnings: list[str] = []

    for item in payload.funds:
        has_code = bool(item.code and re.match(r"^\d{6}$", item.code.strip()))
        has_name = bool(item.name and item.name.strip())

        if has_code and has_name:
            # Cross-check: fetch actual name for the given code
            try:
                info = await fetch_fund_info(item.code.strip())  # type: ignore[union-attr]
                actual_name: str = info.get("name") or ""
                provided_name: str = item.name.strip()  # type: ignore[union-attr]
                # Fuzzy check: provided name should be a substring or vice versa
                if actual_name and provided_name not in actual_name and actual_name not in provided_name:
                    warnings.append(
                        f"代码 {item.code} 对应基金名称为「{actual_name}」，与提供的「{provided_name}」不一致，已按代码导入"
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
                    resolved_items.append(item.model_copy(update={"code": results[0]["code"]}))
                else:
                    unresolved.append(item.name)  # type: ignore[arg-type]
            except Exception:
                unresolved.append(item.name)  # type: ignore[arg-type]

        else:
            unresolved.append(str(item.code or item.name or "unknown"))

    # Merge codes list and funds list into a unified map: code -> extra data
    extra: dict[str, BatchFundItem] = {item.code.strip(): item for item in resolved_items}  # type: ignore[union-attr]
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

    # Fetch all fund infos in parallel
    t_batch = time.perf_counter()

    async def _safe_fetch_info(code: str) -> tuple[str, str | None, str | None]:
        try:
            info = await fetch_fund_info(code)
            return code, info.get("name"), info.get("sector")
        except Exception:
            return code, None, None

    info_results = await asyncio.gather(*[_safe_fetch_info(c) for c in valid])
    fund_info_map: dict[str, tuple[str | None, str | None]] = {r[0]: (r[1], r[2]) for r in info_results}
    logger.info("add_funds_batch: fetched info for %d codes in %.3fs", len(valid), time.perf_counter() - t_batch)

    actually_added: list[str] = []
    with get_conn() as conn:
        for code in valid:
            name, sector = fund_info_map.get(code, (None, None))

            # Reject codes that don't correspond to a real fund (no name returned)
            item = extra.get(code)
            existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
            if not existing and not name:
                invalid.append(code)
                continue
            actually_added.append(code)
            if existing:
                updates = []
                params: list = []
                if name:
                    updates.append("name=?"); params.append(name)
                if sector:
                    updates.append("sector=?"); params.append(sector)
                amt = amounts.get(code)
                if amt is not None:
                    updates.append("amount=?"); params.append(amt)
                if item:
                    if item.holding_amount is not None:
                        updates.append("imported_holding_amount=?"); params.append(item.holding_amount)
                    if item.cumulative_return is not None:
                        updates.append("imported_cumulative_return=?"); params.append(item.cumulative_return)
                    if item.holding_return is not None:
                        updates.append("imported_holding_return=?"); params.append(item.holding_return)
                if updates:
                    params.append(code)
                    conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
            else:
                conn.execute(
                    """INSERT INTO funds
                       (code,name,sector,amount,imported_holding_amount,imported_cumulative_return,imported_holding_return,created_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (code, name, sector, amounts.get(code),
                     item.holding_amount if item else None,
                     item.cumulative_return if item else None,
                     item.holding_return if item else None,
                     now),
                )
        conn.commit()

    # For funds with holding_amount, create a synthetic buy transaction using latest NAV
    tx_now = datetime.now(timezone.utc).isoformat()
    nav_skipped: list[str] = []
    for code in actually_added:
        item = extra.get(code)
        if not item or item.holding_amount is None or item.holding_amount <= 0:
            continue
        try:
            with get_conn() as conn:
                existing_tx = conn.execute(
                    "SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)
                ).fetchone()["c"]
            if existing_tx > 0:
                nav_skipped.append(f"{code}（已有交易记录，跳过）")
                continue

            latest = await fetch_latest_nav(code)
            if not latest or not latest.get("nav"):
                nav_skipped.append(f"{code}（无法获取净值）")
                continue

            nav_val = Decimal(str(latest["nav"]))
            shares_val = (Decimal(str(item.holding_amount)) / nav_val).quantize(Decimal("0.01"))
            if shares_val <= 0:
                nav_skipped.append(f"{code}（计算份额为零）")
                continue

            amount_val = (nav_val * shares_val).quantize(Decimal("0.01"))
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO transactions(code,direction,trade_date,nav,shares,amount,fee,source,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (code, "buy", latest["date"], str(nav_val), str(shares_val),
                     str(amount_val), "0", "import", tx_now),
                )
                _recompute_holding_shares(conn, code)
                conn.commit()
        except Exception as e:
            nav_skipped.append(f"{code}（{e}）")

    if nav_skipped:
        warnings.extend(nav_skipped)

    return {"ok": True, "added": actually_added, "invalid": invalid, "warnings": warnings}


@app.post("/api/funds/{code}")
async def add_fund(code: str, payload: AddFundPayload | None = None) -> dict:
    code = _validate_code(code)
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

    amount = payload.amount if payload else None

    with get_conn() as conn:
        existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
        if existing:
            if amount is not None:
                conn.execute("UPDATE funds SET amount=? WHERE code=?", (amount, code))
            if sector and not conn.execute("SELECT sector FROM funds WHERE code=? AND sector IS NOT NULL", (code,)).fetchone():
                conn.execute("UPDATE funds SET sector=?, name=? WHERE code=?", (sector, name, code))
        else:
            conn.execute(
                "INSERT INTO funds(code,name,sector,amount,created_at) VALUES(?,?,?,?,?)",
                (code, name, sector, amount, now),
            )
        conn.commit()
    return {"ok": True, "code": code, "name": name, "sector": sector}


@app.get("/api/quote/{code}")
async def quote(code: str) -> dict:
    code = _validate_code(code)
    try:
        data = await fetch_realtime_estimate(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return data


@app.get("/api/funds/overview")
async def funds_overview() -> dict:
    with get_conn() as conn:
        funds = [dict(r) for r in conn.execute("SELECT code, name, sector, holding_shares, created_at FROM funds ORDER BY created_at DESC").fetchall()]

    t0 = time.perf_counter()

    async def _fetch_one(f: dict) -> dict:
        code = f["code"]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT code,name,gsz,gszzl,gztime,captured_at FROM fund_snapshots WHERE code=? ORDER BY id DESC LIMIT 1",
                (code,),
            ).fetchone()
            tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)).fetchone()["c"]

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
    logger.info("funds_overview: %d funds fetched in %.3fs", len(funds), time.perf_counter() - t0)
    return {"items": items}


@app.post("/api/snapshots/pull")
async def pull_snapshots() -> dict:
    with get_conn() as conn:
        codes = [r["code"] for r in conn.execute("SELECT code FROM funds").fetchall()]

    captured_at = datetime.now(timezone.utc).isoformat()

    async def _safe_fetch(code: str) -> tuple[str, dict | None]:
        try:
            return code, await fetch_realtime_estimate(code)
        except Exception:
            return code, None

    results = await asyncio.gather(*[_safe_fetch(c) for c in codes])

    inserted = 0
    with get_conn() as conn:
        for code, d in results:
            if d is None:
                continue
            conn.execute(
                """
                INSERT INTO fund_snapshots(code,name,dwjz,gsz,gszzl,gztime,captured_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    code,
                    d.get("name"),
                    d.get("dwjz"),
                    d.get("gsz"),
                    d.get("gszzl"),
                    d.get("gztime"),
                    captured_at,
                ),
            )
            inserted += 1
        conn.commit()

    return {"ok": True, "codes": len(codes), "inserted": inserted, "captured_at": captured_at}


@app.get("/api/snapshots/{code}")
def get_snapshots(code: str, limit: int = 50) -> dict:
    code = _validate_code(code)
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT code,name,dwjz,gsz,gszzl,gztime,captured_at
            FROM fund_snapshots
            WHERE code=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (code, limit),
        ).fetchall()
    items = [dict(r) for r in rows]
    items.reverse()
    return {"code": code, "count": len(items), "items": items}


@app.get("/api/funds/{code}/holdings")
async def get_fund_holdings(code: str) -> dict:
    code = _validate_code(code)
    try:
        holdings = await fetch_fund_holdings(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "count": len(holdings), "holdings": holdings}


@app.get("/api/funds/{code}/detail")
async def get_fund_detail(code: str) -> dict:
    """Comprehensive fund detail: manager, size, period returns, asset allocation."""
    code = _validate_code(code)
    try:
        detail = await fetch_fund_detail(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return detail


@app.get("/api/funds/{code}/nav-history")
async def get_nav_history(code: str, limit: int = 365) -> dict:
    """Historical NAV data for charting."""
    code = _validate_code(code)
    limit = max(1, min(limit, 1000))
    try:
        history = await fetch_nav_history(code, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "count": len(history), "history": history}


@app.get("/api/funds/{code}/nav-on")
async def get_nav_on_date(code: str, date: str) -> dict:
    """Return the NAV for a specific date (YYYY-MM-DD)."""
    code = _validate_code(code)
    try:
        nav = await fetch_nav_on_date(code, date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"code": code, "date": date, "nav": nav}


@app.delete("/api/funds/{code}")
def delete_fund(code: str) -> dict:
    """Remove a fund from the watchlist."""
    code = _validate_code(code)
    with get_conn() as conn:
        existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="fund not found")
        conn.execute("DELETE FROM fund_snapshots WHERE code=?", (code,))
        conn.execute("DELETE FROM transactions WHERE code=?", (code,))
        conn.execute("DELETE FROM funds WHERE code=?", (code,))
        conn.commit()
    return {"ok": True, "code": code}


@app.get("/api/portfolio/summary")
async def portfolio_summary() -> dict:
    """Aggregated portfolio stats: total value, daily return, cumulative return."""
    with get_conn() as conn:
        funds = [dict(r) for r in conn.execute(
            "SELECT code, name, holding_shares FROM funds WHERE holding_shares IS NOT NULL ORDER BY created_at DESC"
        ).fetchall()]

    t0 = time.perf_counter()

    # I2 fix: batch-compute PnL for all funds in ONE DB connection before async gather
    pnl_map: dict[str, dict] = {}
    codes = [f["code"] for f in funds if f.get("holding_shares") and Decimal(f["holding_shares"]) > 0]
    if codes:
        with get_conn() as conn:
            for code in codes:
                pnl_map[code] = _compute_pnl(conn, code)

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
        daily_change = float(q.get("gszzl", 0)) if q.get("gszzl") else 0.0
        current_value = (shares * nav).quantize(Decimal("0.01"))
        daily_return_val = (current_value * Decimal(str(daily_change)) / 100).quantize(Decimal("0.01"))
        pnl = pnl_map.get(code, {})
        cost = Decimal(pnl.get("total_cost", "0"))
        total_return = current_value - cost
        return_rate = (total_return / cost * 100).quantize(Decimal("0.01")) if cost > 0 else Decimal("0")
        return {
            "code": code,
            "name": f["name"] or q.get("name"),
            "shares": str(shares),
            "nav": str(nav),
            "daily_change": daily_change,
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
    logger.info("portfolio_summary: %d funds fetched in %.3fs", len(funds), time.perf_counter() - t0)

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
        notx_funds = [dict(r) for r in conn.execute(
            """SELECT code, name,
                      COALESCE(imported_holding_amount, amount) AS holding_amount,
                      imported_cumulative_return,
                      imported_holding_return
               FROM funds
               WHERE holding_shares IS NULL
                 AND COALESCE(imported_holding_amount, amount) > 0
               ORDER BY created_at DESC"""
        ).fetchall()]

    async def _fetch_notx(f: dict) -> dict:
        code = f["code"]
        amount = Decimal(str(f["holding_amount"]))
        daily_change = 0.0
        daily_return_val = Decimal("0")
        try:
            q = await fetch_realtime_estimate(code)
            gszzl = q.get("gszzl")
            if gszzl is not None:
                daily_change = float(gszzl)
                daily_return_val = (amount * Decimal(str(daily_change)) / 100).quantize(Decimal("0.01"))
        except Exception:
            pass
        cum_ret = f.get("imported_cumulative_return")
        hold_ret = f.get("imported_holding_return")
        return {
            "code": code,
            "name": f["name"],
            "shares": None,
            "nav": None,
            "daily_change": daily_change,
            "current_value": str(amount),
            "daily_return": str(daily_return_val),
            "total_cost": None,
            "total_return": str(Decimal(str(hold_ret or 0)).quantize(Decimal("0.01"))),
            "return_rate": None,
            "imported_cumulative_return": str(Decimal(str(cum_ret or 0)).quantize(Decimal("0.01"))),
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
        (total_current_with_cost - total_cost) / total_cost * 100
    ).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    return {
        "total_current": str(total_current),
        "total_cost": str(total_cost),
        "total_daily_return": str(total_daily_return),
        "total_return": str((total_current - total_cost).quantize(Decimal("0.01"))),
        "total_return_rate": str(total_return_rate),
        "fund_count": len(items),
        "items": items,
    }


@app.patch("/api/funds/{code}")
def update_fund(code: str, payload: UpdateFundPayload) -> dict:
    code = _validate_code(code)
    with get_conn() as conn:
        # If has transactions, reject manual shares edit
        if payload.holding_shares is not None:
            tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE code=?", (code,)).fetchone()["c"]
            if tx_count > 0:
                raise HTTPException(status_code=400, detail="有交易记录时不可手动编辑份额")
            try:
                Decimal(payload.holding_shares)
            except InvalidOperation:
                raise HTTPException(status_code=400, detail="无效的份额数值")

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


@app.get("/api/portfolio/history")
async def portfolio_history(limit: int = 90) -> dict:
    """Portfolio value history: holdings at each date × confirmed NAV, plus today's estimate.

    For funds with transactions: per-date shares reconstructed from transaction log × NAV.
    For imported funds without transactions: implied shares = holding_amount / latest_nav × NAV.
    """
    limit = max(1, min(limit, 365))

    from collections import defaultdict

    with get_conn() as conn:
        transactions = [
            dict(r) for r in conn.execute(
                "SELECT code, direction, trade_date, shares FROM transactions ORDER BY trade_date ASC"
            ).fetchall()
        ]
        current_holdings = {
            r["code"]: Decimal(r["holding_shares"])
            for r in conn.execute(
                "SELECT code, holding_shares FROM funds WHERE holding_shares IS NOT NULL"
            ).fetchall()
            if r["holding_shares"] and Decimal(r["holding_shares"]) > 0
        }
        # Imported funds without any transactions: use holding_amount to infer shares
        imported_funds: dict[str, Decimal] = {
            r["code"]: Decimal(str(r["holding_amount"]))
            for r in conn.execute(
                """SELECT code, COALESCE(imported_holding_amount, amount) AS holding_amount
                   FROM funds
                   WHERE holding_shares IS NULL
                     AND COALESCE(imported_holding_amount, amount) > 0"""
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

    async def _fetch_code(code: str) -> tuple[str, dict[str, float], float | None]:
        nav_dict: dict[str, float] = {}
        gsz: float | None = None
        try:
            hist = await fetch_nav_history(code, limit=limit + 30)
            nav_dict = {h["date"]: float(h["nav"]) for h in hist if h.get("date") and h.get("nav") is not None}
        except Exception:
            pass
        try:
            q = await fetch_realtime_estimate(code)
            raw = q.get("gsz")
            if raw:
                gsz = float(raw)
        except Exception:
            pass
        return code, nav_dict, gsz

    fetch_results = await asyncio.gather(*[_fetch_code(c) for c in all_codes])

    nav_map: dict[str, dict[str, float]] = {}
    gsz_map: dict[str, float] = {}
    for code, nav_dict, gsz in fetch_results:
        nav_map[code] = nav_dict
        if gsz:
            gsz_map[code] = gsz

    # Implied shares for imported funds: holding_amount ÷ latest confirmed NAV
    implied_shares: dict[str, float] = {}
    excluded_codes: list[str] = []
    for code, holding_amount in imported_funds.items():
        nav_dict = nav_map.get(code, {})
        if nav_dict:
            latest_nav = nav_dict[max(nav_dict.keys())]
            if latest_nav > 0:
                implied_shares[code] = float(holding_amount) / latest_nav
        else:
            # I6 fix: log and collect codes excluded due to missing NAV data
            excluded_codes.append(code)
            logger.warning("portfolio_history: no NAV data for %s, excluded from chart", code)

    all_dates = sorted({d for nd in nav_map.values() for d in nd})
    all_dates = all_dates[-limit:]

    date_totals: dict[str, float] = {}
    for target_date in all_dates:
        total = 0.0
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
            total += float(shares) * nav
        # Imported funds without transactions: implied shares × that day's NAV
        for code, imp_shares in implied_shares.items():
            nav = nav_map.get(code, {}).get(target_date)
            if nav is None:
                continue
            total += imp_shares * nav
        if total > 0:
            date_totals[target_date] = total

    # Today's estimated point using gsz; only insert if date not already in confirmed data
    CST = timezone(timedelta(hours=8))
    today = datetime.now(CST).strftime("%Y-%m-%d")
    today_total = sum(
        float(current_holdings[code]) * gsz
        for code, gsz in gsz_map.items()
        if code in current_holdings
    )
    # C1 fix: use implied_shares × gsz (market value) not holding_amount (cost basis)
    for code, imp_shares in implied_shares.items():
        gsz = gsz_map.get(code)
        if gsz:
            today_total += imp_shares * gsz
        else:
            today_total += float(imported_funds[code])  # fallback to holding_amount
    # C2 fix: setdefault — don't overwrite an already-confirmed NAV for today
    if today_total > 0:
        date_totals.setdefault(today, today_total)

    sorted_items = sorted(date_totals.items())
    result: dict = {
        "count": len(sorted_items),
        "history": [
            {"date": date, "total_value": round(value, 2)}
            for date, value in sorted_items
        ],
    }
    if excluded_codes:
        result["excluded_codes"] = excluded_codes  # I6: surface missing-NAV funds to caller
    return result


@app.get("/api/market/indices")
async def market_indices() -> dict:
    """Major domestic and overseas market indices from eastmoney."""
    try:
        items = await fetch_market_indices()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"items": items}


@app.get("/api/cron/status")
def cron_status() -> dict:
    """Return the snapshot scheduler state."""
    return {
        "interval_minutes": 5,
        "trading_hours": "09:25-11:35, 12:55-15:05 CST (周一至周五)",
        **_cron_state,
    }


@app.get("/api/funds/search")
async def search_funds(q: str = "") -> dict:
    """Search funds by name or code keyword via eastmoney."""
    q = q.strip()
    if not q:
        return {"results": []}
    if len(q) > 50:
        raise HTTPException(status_code=400, detail="搜索词过长（最多 50 个字符）")
    results = await search_fund_by_name(q, limit=10)
    return {"results": results}


@app.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, codes = extract_fund_codes_from_image(path)
    _, matched_funds = extract_funds_with_amounts(path)

    # If no codes found, try to extract fund names and search for codes
    name_matches: list[dict] = []
    if not codes:
        fund_names = extract_fund_names_from_text(raw_text)
        seen_codes: set[str] = set()
        for name in fund_names[:5]:  # limit to avoid too many API calls
            try:
                results = await search_fund_by_name(name, limit=1)
                for r in results:
                    if r["code"] not in seen_codes:
                        seen_codes.add(r["code"])
                        name_matches.append({
                            "code": r["code"],
                            "name": r.get("name", ""),
                            "matched_keyword": name,
                            "type": r.get("type"),
                        })
            except Exception:
                continue
        # Add name-matched codes to the codes list
        codes = list(seen_codes)

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at) VALUES(?,?,?,?)",
            (path.name, raw_text, json.dumps(codes, ensure_ascii=False), now),
        )
        conn.commit()

    return {
        "ok": True,
        "image": path.name,
        "matched_codes": codes,
        "matched_funds": matched_funds if matched_funds else name_matches,
        "name_matches": name_matches,
        "raw_text": raw_text,
        "saved_at": now,
    }


# ── Transaction endpoints ──────────────────────────────────────────


@app.get("/api/funds/{code}/transactions")
def list_transactions(code: str) -> dict:
    code = _validate_code(code)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE code=? ORDER BY trade_date DESC, id DESC",
            (code,),
        ).fetchall()
    return {"code": code, "items": [dict(r) for r in rows]}


@app.post("/api/funds/{code}/transactions")
def add_transaction(code: str, payload: AddTransactionPayload) -> dict:
    code = _validate_code(code)
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
        _recompute_holding_shares(conn, code)
        conn.commit()

    return {"ok": True, "code": code}


@app.delete("/api/transactions/{tx_id}")
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
        _recompute_holding_shares(conn, code)
        conn.commit()
    return {"ok": True, "deleted": tx_id}


@app.get("/api/funds/{code}/pnl")
async def get_pnl(code: str) -> dict:
    code = _validate_code(code)
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
        pnl = _compute_pnl(conn, code, current_nav)

    return {"code": code, "has_transactions": True, **pnl}


@app.post("/api/transactions/csv")
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
            _recompute_holding_shares(conn, c)
        conn.commit()

    return {"ok": True, "imported": imported, "skipped": skipped, "errors": errors}


@app.post("/api/ocr/transaction")
async def ocr_transaction(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_tx_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, tx_data = extract_transaction_from_image(path)

    return {
        "ok": True,
        "image": path.name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
