"""Integration tests for GET /api/stocks/{code}/funds.

Mocks the eastmoney datacenter (RPT_MAINDATA_MAIN_POSITIONDETAILS) via
pytest-httpx so tests run fully offline.

Covers:
- Normal path: returns parsed fund list with correct field mapping
- Quarter fallback: first quarter returns count=0, second quarter returns data
- 502 on network error
- 400 on invalid stock code
"""

from __future__ import annotations

import json

import app.db as app_db
import app.fund_source as fund_source
import httpx
import pytest
from app.main import app as fastapi_app

from tests.client import ASGISyncClient

# ── Canned responses ─────────────────────────────────────────────────────────

_FUND_ROW = {
    "SECURITY_CODE": "600519",
    "SECURITY_NAME_ABBR": "贵州茅台",
    "REPORT_DATE": "2024-12-31 00:00:00",
    "HOLDER_CODE": "510050",
    "HOLDER_NAME": "华夏上证50ETF",
    "HOLD_MARKET_CAP": 17980472040,
    "TOTAL_SHARES": 11800000,
    "NETASSET_RATIO": 11.87,
    "PARENT_ORG_NAME": "华夏基金管理有限公司",
    "ORG_TYPE": "基金",
}

_EMPTY_RESULT = json.dumps(
    {
        "version": "v1",
        "result": {"pages": 0, "data": [], "count": 0},
        "success": True,
        "message": "ok",
        "code": 0,
    }
).encode()

_DATA_RESULT = json.dumps(
    {
        "version": "v1",
        "result": {"pages": 10, "data": [_FUND_ROW], "count": 1600},
        "success": True,
        "message": "ok",
        "code": 0,
    }
).encode()


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def stock_client(tmp_path, monkeypatch):
    """TestClient backed by a temp DB; lifespan not started (no scheduler)."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    return ASGISyncClient(fastapi_app)


@pytest.fixture
def no_retry_sleep(monkeypatch):
    """Skip retry backoff inside fund_source."""
    import asyncio as _asyncio

    class _FastAsyncio:
        def __getattr__(self, name):
            return getattr(_asyncio, name)

        @staticmethod
        async def sleep(_delay):
            return None

    monkeypatch.setattr(fund_source, "asyncio", _FastAsyncio())


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestFundsHoldingStock:
    def test_success_parses_fields(self, stock_client, httpx_mock):
        """Normal path: first quarter has data, fields mapped correctly."""
        # The function will try the most recent quarter first; mock that one.
        httpx_mock.add_response(content=_DATA_RESULT)

        resp = stock_client.get("/api/stocks/600519/funds?limit=50")
        assert resp.status_code == 200
        body = resp.json()

        assert body["stock_code"] == "600519"
        assert body["stock_name"] == "贵州茅台"
        assert body["count"] == 1600
        assert body["report_date"] is not None

        items = body["items"]
        assert len(items) == 1
        item = items[0]
        assert item["code"] == "510050"
        assert item["name"] == "华夏上证50ETF"
        assert item["hold_market_cap"] == 17980472040
        assert item["shares"] == 11800000
        assert item["netasset_ratio"] == 11.87
        assert item["company"] == "华夏基金管理有限公司"

    def test_quarter_fallback(self, stock_client, httpx_mock):
        """First quarter returns count=0; second quarter returns data."""
        httpx_mock.add_response(content=_EMPTY_RESULT)  # first quarter: empty
        httpx_mock.add_response(content=_DATA_RESULT)  # second quarter: data

        resp = stock_client.get("/api/stocks/600519/funds")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1600
        assert len(body["items"]) == 1

    def test_all_quarters_empty_returns_zero(self, stock_client, httpx_mock):
        """When all 4 quarters return empty, route returns count=0."""
        for _ in range(4):
            httpx_mock.add_response(content=_EMPTY_RESULT)

        resp = stock_client.get("/api/stocks/600519/funds")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["items"] == []

    def test_network_error_returns_502(self, stock_client, httpx_mock, no_retry_sleep):
        """Network failure → 502 with detail message."""
        for _ in range(3):  # cover retries
            httpx_mock.add_exception(httpx.ConnectError("refused"))

        resp = stock_client.get("/api/stocks/600519/funds")
        assert resp.status_code == 502
        assert "不可用" in resp.json()["detail"]

    def test_invalid_code_returns_400(self, stock_client):
        """Non-6-digit code → 400."""
        resp = stock_client.get("/api/stocks/abc/funds")
        assert resp.status_code == 400

    def test_limit_cap(self, stock_client, httpx_mock):
        """limit > 200 is capped at 200 (no server error)."""
        httpx_mock.add_response(content=_DATA_RESULT)
        resp = stock_client.get("/api/stocks/600519/funds?limit=9999")
        assert resp.status_code == 200
