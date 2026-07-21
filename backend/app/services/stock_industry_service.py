"""Stock industry lookup: local table first, eastmoney for the rest."""

from __future__ import annotations

import logging

from ..core import utc_now_iso
from ..db import get_conn
from ..fund_source import fetch_stock_industries_from_source
from ..repositories import stock_industry_repo

logger = logging.getLogger(__name__)


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

    now = utc_now_iso()
    rows_to_write = [
        (code, name, industry, now)
        for code, (name, industry) in fetched.items()
        if industry
    ]
    if rows_to_write:
        try:
            with get_conn() as conn:
                stock_industry_repo.upsert_bulk(conn, rows_to_write)
                conn.commit()
        except Exception:
            logger.exception(
                "get_stock_industries: failed to write back %d rows",
                len(rows_to_write),
            )

    for code, (_name, industry) in fetched.items():
        if industry:
            result[code] = industry

    return result
