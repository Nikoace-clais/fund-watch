"""Tests for stock industry enrichment (get_stock_industries)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.fund_source import _secid
from app.services.stock_industry_service import get_stock_industries

# ── secid prefix helper ───────────────────────────────────────────────────────


def test_secid_shanghai() -> None:
    assert _secid("600519") == "1"  # 贵州茅台
    assert _secid("900001") == "1"  # B shares (9x)


def test_secid_shenzhen() -> None:
    assert _secid("000858") == "0"  # 五粮液
    assert _secid("300750") == "0"  # CATL
    assert _secid("430047") == "0"  # 北交所


# ── fetch_stock_industries: hits local table, skips API ──────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path) -> str:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE stock_industry (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            industry   TEXT,
            updated_at TEXT NOT NULL
        )"""
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO stock_industry VALUES (?, ?, ?, ?)",
        ("600519", "贵州茅台", "白酒Ⅱ", now),
    )
    conn.execute(
        "INSERT INTO stock_industry VALUES (?, ?, ?, ?)",
        ("000858", "五粮液", "白酒Ⅱ", now),
    )
    conn.commit()
    conn.close()
    return str(db)


@pytest.mark.asyncio
async def test_hits_local_table_no_api(tmp_db: str) -> None:
    """Table hit → API client must NOT be called."""
    with (
        patch.dict(os.environ, {"FUND_WATCH_DB": tmp_db}),
        patch("app.fund_source._get_client") as mock_client,
    ):
        result = await get_stock_industries(["600519", "000858"])

    mock_client.assert_not_called()
    assert result == {"600519": "白酒Ⅱ", "000858": "白酒Ⅱ"}


@pytest.mark.asyncio
async def test_unknown_code_skipped_gracefully(tmp_db: str) -> None:
    """Unknown code with failed API → returns partial result, no crash."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = {"data": None}  # empty/bad response

    mock_http = AsyncMock()
    mock_http.get.return_value = mock_resp

    with (
        patch.dict(os.environ, {"FUND_WATCH_DB": tmp_db}),
        patch("app.fund_source._get_client", return_value=mock_http),
    ):
        result = await get_stock_industries(["600519", "999999"])

    # 600519 from table, 999999 has no industry → omitted
    assert result["600519"] == "白酒Ⅱ"
    assert "999999" not in result


@pytest.mark.asyncio
async def test_fetch_success_writes_back_and_then_hits_local_table(
    tmp_db: str,
) -> None:
    """New code fetched from the API is written to stock_industry, and a
    subsequent lookup for the same code hits the local table instead of
    calling the API again."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = {
        "data": {"f57": "300750", "f58": "宁德时代", "f127": "电池"}
    }
    mock_http = AsyncMock()
    mock_http.get.return_value = mock_resp

    with (
        patch.dict(os.environ, {"FUND_WATCH_DB": tmp_db}),
        patch("app.fund_source._get_client", return_value=mock_http),
    ):
        result = await get_stock_industries(["300750"])

    assert result["300750"] == "电池"

    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT stock_code, stock_name, industry FROM stock_industry"
        " WHERE stock_code=?",
        ("300750",),
    ).fetchone()
    conn.close()
    assert row == ("300750", "宁德时代", "电池")

    with (
        patch.dict(os.environ, {"FUND_WATCH_DB": tmp_db}),
        patch("app.fund_source._get_client") as mock_client_2,
    ):
        result2 = await get_stock_industries(["300750"])

    mock_client_2.assert_not_called()
    assert result2["300750"] == "电池"
