"""Batch fund import: resolve codes/names, register funds, seed positions."""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

from ..core import is_valid_code
from ..fund_source import (
    fetch_fund_info,
    fetch_latest_nav,
    search_fund_by_name,
)
from ..repositories import funds_repo, portfolios_repo, positions_repo, tx_repo
from ..schemas import BatchFundItem, BatchFundsPayload
from .holdings import recompute_holding_shares

logger = logging.getLogger(__name__)


async def import_funds_batch(
    conn: sqlite3.Connection, payload: BatchFundsPayload
) -> dict[str, Any]:
    """Resolve and persist a batch of funds; returns the API response payload."""
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

    extra: dict[str, BatchFundItem] = {}
    for item in resolved_items:
        assert item.code is not None
        extra[item.code.strip()] = item
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
        entry = extra.get(code)

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
                float(entry.holding_amount)
                if entry and entry.holding_amount is not None
                else None
            ),
            imported_cumulative_return=(
                float(entry.cumulative_return)
                if entry and entry.cumulative_return is not None
                else None
            ),
            imported_holding_return=(
                float(entry.holding_return)
                if entry and entry.holding_return is not None
                else None
            ),
        )
        actually_added.append(code)

    # ── Synthetic buy transaction for imported holding amounts ────────────────
    tx_now = datetime.now(timezone.utc).isoformat()
    nav_skipped: list[str] = []
    candidates: list[tuple[str, Decimal]] = []
    for code in actually_added:
        entry = extra.get(code)
        if not entry or entry.holding_amount is None or entry.holding_amount <= 0:
            continue
        if tx_repo.count_for_portfolio_code(conn, pf_id, code) > 0:
            nav_skipped.append(f"{code}（已有交易记录，跳过）")
            continue
        candidates.append((code, entry.holding_amount))

    async def _safe_fetch_nav(
        code: str,
    ) -> tuple[str, dict[str, Any] | None, Exception | None]:
        try:
            return code, await fetch_latest_nav(code), None
        except Exception as e:
            return code, None, e

    nav_results = await asyncio.gather(*[_safe_fetch_nav(c) for c, _ in candidates])
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
