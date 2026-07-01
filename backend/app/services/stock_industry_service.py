"""Stock industry lookup: local table first, eastmoney for the rest."""

from __future__ import annotations

from datetime import datetime, timezone

from ..db import get_conn
from ..fund_source import fetch_stock_industries_from_source
from ..repositories import stock_industry_repo


async def get_stock_industries(codes: list[str]) -> dict[str, str]:
    """Return {stock_code: industry}. Only codes missing from the local table
    hit the eastmoney API; results are written back so they accumulate
    across restarts.
    """
    if not codes:
        return {}

    with get_conn() as conn:
        result = stock_industry_repo.get_bulk(conn, codes)

    missing = [c for c in codes if c not in result]
    if not missing:
        return result

    fetched = await fetch_stock_industries_from_source(missing)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows_to_write = [
        (code, name, industry, now)
        for code, (name, industry) in fetched.items()
        if industry
    ]
    if rows_to_write:
        with get_conn() as conn:
            stock_industry_repo.upsert_bulk(conn, rows_to_write)
            conn.commit()

    for code, (_name, industry) in fetched.items():
        if industry:
            result[code] = industry

    return result
