"""Integration tests for GET /api/market/indices (Sina Finance source).

Mocks hq.sinajs.cn responses (GBK encoded) via pytest-httpx so tests run
fully offline, covering all four line formats: A-share (sh/sz), HK (hk),
US (gb_) and Nikkei (b_NKY).
"""

import asyncio

import app.db as app_db
import app.fund_source as fund_source
import httpx
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient

# Real samples captured from hq.sinajs.cn on 2026-06-10
_US_NKY_LINES = (
    'var hq_str_gb_$dji="道琼斯,50872.1094,0.17,2026-06-10 06:06:45,86.1000,'
    "50814.4219,51260.9219,50211.1211,51660.3984,41981.1406,576863889,581755415,"
    "0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.0000,,Jun 9 06:06PM EDT,"
    '50786.0117,0,1,2026";\n'
    'var hq_str_gb_$inx="标普500指数,7386.6499,-0.26,2026-06-10 04:20:25,-19.0800,'
    "7438.6602,7483.1499,7237.8501,7620.8999,5943.2300,3426321507,3509670750,"
    "0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.0000,,Jun 9 04:20PM EDT,"
    '7405.7300,0,1,2026";\n'
    'var hq_str_gb_ixic="纳斯达克,25678.8219,-0.97,2026-06-10 05:30:00,-250.8407,'
    "26110.3128,26259.9222,24980.3763,27190.2070,19334.9824,10787986837,8531372331,"
    "0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.00,,Jun 09 05:16PM EDT,"
    '25929.6626,0,1,2026,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000";\n'
    'var hq_str_b_NKY="日经225指数,63878.2500,-1538.38,-2.35,2:12 AM,14:12:00,'
    '2026-06-10,12:59:25,64952.3800,65416.6300,65098.8600,63777.7700,0";\n'
)

# A-share lines follow the parser's expectation:
# parts[1] = previous_close, parts[3] = current
_A_SHARE_LINES = (
    'var hq_str_sh000001="上证指数,3400.0000,3398.0000,3434.0000,3450.0000,'
    '3380.0000,0,0,1,2";\n'
    'var hq_str_sz399001="深证成指,11000.0000,10990.0000,11110.0000,11200.0000,'
    '10900.0000,0,0,1,2";\n'
    'var hq_str_sz399006="创业板指,2200.0000,2190.0000,2178.0000,2210.0000,'
    '2170.0000,0,0,1,2";\n'
    'var hq_str_sh000300="沪深300,4000.0000,3990.0000,4040.0000,4050.0000,'
    '3980.0000,0,0,1,2";\n'
    'var hq_str_sh000016="上证50,2700.0000,2690.0000,2727.0000,2730.0000,'
    '2680.0000,0,0,1,2";\n'
    'var hq_str_sh000905="中证500,6000.0000,5990.0000,6060.0000,6070.0000,'
    '5980.0000,0,0,1,2";\n'
)

# HK line: parts[6] = current, parts[7] = change, parts[8] = change_percent
_HK_LINE = (
    'var hq_str_hkHSI="HSI,恒生指数,26000.000,26100.000,26500.000,25900.000,'
    '26260.000,260.000,1.000,0.000,0.000,0,0,26500.000,25000.000,2026/06/10,16:08";\n'
)

_FULL_RESPONSE = _A_SHARE_LINES + _HK_LINE + _US_NKY_LINES


@pytest.fixture
def market_client(tmp_path, monkeypatch):
    """TestClient backed by a fresh temp DB; no lifespan (no scheduler)."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    return TestClient(fastapi_app)


@pytest.fixture
def no_retry_sleep(monkeypatch):
    """Skip the retry backoff sleeps inside fund_source only."""

    class _FastAsyncio:
        def __getattr__(self, name):
            return getattr(asyncio, name)

        @staticmethod
        async def sleep(_delay):
            return None

    monkeypatch.setattr(fund_source, "asyncio", _FastAsyncio())


def _by_code(items: list[dict]) -> dict[str, dict]:
    return {item["code"]: item for item in items}


class TestMarketIndices:
    def test_success_all_formats(self, market_client, httpx_mock):
        httpx_mock.add_response(content=_FULL_RESPONSE.encode("gbk"))

        resp = market_client.get("/api/market/indices")
        assert resp.status_code == 200
        body = resp.json()
        assert "error" not in body
        items = body["items"]
        assert len(items) == 11

        by_code = _by_code(items)

        # region drives the frontend domestic/international split
        assert sum(1 for i in items if i["region"] == "domestic") == 6
        assert sum(1 for i in items if i["region"] == "international") == 5

        # US (gb_ prefix): parts[1]=value, parts[2]=pct, parts[4]=change
        dji = by_code["DJI"]
        assert dji["name"] == "道琼斯"
        assert dji["region"] == "international"
        assert dji["value"] == 50872.11
        assert dji["change"] == 86.10
        assert dji["change_percent"] == 0.17

        spx = by_code["SPX"]
        assert spx["name"] == "标普500"  # config name, not "标普500指数" from response
        assert spx["value"] == 7386.65
        assert spx["change"] == -19.08
        assert spx["change_percent"] == -0.26

        assert by_code["IXIC"]["value"] == 25678.82
        assert by_code["IXIC"]["change"] == -250.84

        # Nikkei (b_NKY): parts[1]=value, parts[2]=change, parts[3]=pct
        nky = by_code["N225"]
        assert nky["name"] == "日经225"
        assert nky["value"] == 63878.25
        assert nky["change"] == -1538.38
        assert nky["change_percent"] == -2.35

        # HK: parts[6]=value, parts[7]=change, parts[8]=pct
        hsi = by_code["HSI"]
        assert hsi["value"] == 26260.0
        assert hsi["change"] == 260.0
        assert hsi["change_percent"] == 1.0

        # A-share: change derived from previous_close (parts[1]) and current (parts[3])
        sse = by_code["000001"]
        assert sse["name"] == "上证指数"
        assert sse["region"] == "domestic"
        assert sse["value"] == 3434.0
        assert sse["change"] == 34.0
        assert sse["change_percent"] == 1.0

    def test_network_failure_returns_empty_items(
        self, market_client, httpx_mock, no_retry_sleep
    ):
        # Cover all 3 retry attempts
        for _ in range(3):
            httpx_mock.add_exception(httpx.ConnectError("connection refused"))

        resp = market_client.get("/api/market/indices")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["error"]

    def test_corrupted_line_is_skipped(self, market_client, httpx_mock):
        # hkHSI line truncated to fewer than 9 fields -> skipped, rest kept
        broken_hk = 'var hq_str_hkHSI="HSI,恒生指数,26000.000";\n'
        response = _A_SHARE_LINES + broken_hk + _US_NKY_LINES
        httpx_mock.add_response(content=response.encode("gbk"))

        resp = market_client.get("/api/market/indices")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 10

        by_code = _by_code(items)
        assert "HSI" not in by_code
        assert by_code["DJI"]["value"] == 50872.11
        assert by_code["000001"]["value"] == 3434.0
