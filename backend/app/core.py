"""Shared constants and helpers used across routers and services."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, TypeVar

from fastapi import HTTPException

from .repositories import portfolios_repo

T = TypeVar("T")

CST = timezone(timedelta(hours=8))

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

# ASCII-only digits: str.isdigit() also accepts non-decimal Unicode "digit"
# characters (e.g. superscripts) that aren't valid fund/stock codes.
_CODE_RE = re.compile(r"^[0-9]{6}$")


def is_valid_code(code: str) -> bool:
    """True if code is a bare 6-digit fund/stock code (no whitespace stripping)."""
    return bool(code) and bool(_CODE_RE.match(code))


def validate_code(code: str) -> str:
    code = code.strip()
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code


def resolve_portfolio(conn: sqlite3.Connection, portfolio_id: int | None) -> int:
    """Return portfolio_id, defaulting to the first portfolio if none given."""
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="组合不存在")
        return portfolio_id
    first_id = portfolios_repo.first_id(conn)
    if first_id is None:
        raise HTTPException(status_code=404, detail="尚无组合，请先导入基金建立组合")
    return first_id


async def fetch_502(coro: Awaitable[T]) -> T:
    """Await an upstream fetch, mapping any failure to HTTP 502."""
    try:
        return await coro
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def sse(obj: dict[str, Any]) -> str:
    """Format one SSE data frame."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def extract_json(s: str) -> Any:
    """Parse model output as JSON.

    Strips markdown fences; tolerates prefix/suffix text around the first
    balanced JSON array/object (thinking models often emit trailing prose).
    """
    s = s.strip()
    if not s:
        raise ValueError("模型返回空响应")
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    decoder = json.JSONDecoder()
    starts = [0] + sorted(i for i in (s.find("["), s.find("{")) if i > 0)
    for start in starts:
        try:
            return decoder.raw_decode(s, start)[0]
        except json.JSONDecodeError:
            continue
    raise ValueError(f"模型返回了无法解析的 JSON: {s[:120]}")
