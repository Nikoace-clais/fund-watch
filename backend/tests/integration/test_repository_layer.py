"""Regression coverage for the PR1 repository-layer refactor.

Focuses on the two behavior changes that matter: funds_overview no longer
does one DB round-trip per fund (bulk repo queries), and portfolio_holdings
no longer double-fetches realtime estimates via a router-to-router call.
"""
import app.db as app_db
import app.routers.funds as funds_router
import app.services.portfolio_service as portfolio_service
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()

    async def fake_fetch_fund_info(code: str) -> dict:
        return {"name": f"测试基金{code}", "sector": "测试板块"}

    monkeypatch.setattr(funds_router, "fetch_fund_info", fake_fetch_fund_info)
    return TestClient(fastapi_app)


class TestFundsOverviewBulk:
    def test_overview_reports_correct_snapshot_and_tx_count_per_fund(
        self, app_client, monkeypatch
    ):
        for code in ("110011", "161725"):
            resp = app_client.post(f"/api/funds/{code}")
            assert resp.status_code == 200

        pf_id = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5",
                "shares": "100",
                "portfolio_id": pf_id,
            },
        )

        async def fake_estimate(code: str) -> dict:
            return {
                "name": f"测试基金{code}",
                "gsz": "1.6",
                "gszzl": "1.0",
                "gztime": "15:00",
            }

        monkeypatch.setattr(funds_router, "fetch_realtime_estimate", fake_estimate)

        resp = app_client.get("/api/funds/overview")
        assert resp.status_code == 200
        items = {it["fund"]["code"]: it for it in resp.json()["items"]}

        assert items["110011"]["has_transactions"] is True
        assert items["161725"]["has_transactions"] is False
        # Neither snapshot in the DB yet: both fall back to the live estimate.
        assert items["110011"]["latest"]["gsz"] == "1.6"
        assert items["161725"]["latest"]["gsz"] == "1.6"


class TestPortfolioHoldingsNoDoubleFetch:
    def test_holdings_fetches_realtime_estimate_once_per_code(
        self, app_client, monkeypatch
    ):
        app_client.post("/api/funds/110011")
        pf_id = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5",
                "shares": "100",
                "portfolio_id": pf_id,
            },
        )

        call_count = {"n": 0}

        async def fake_estimate(code: str) -> dict:
            call_count["n"] += 1
            return {"name": "测试基金110011", "gsz": "1.6", "gszzl": "1.0"}

        async def fake_holdings(code: str) -> list:
            return []

        async def fake_industries(codes: list) -> dict:
            return {}

        monkeypatch.setattr(portfolio_service, "fetch_realtime_estimate", fake_estimate)
        import app.routers.portfolio as portfolio_router

        monkeypatch.setattr(portfolio_router, "fetch_fund_holdings", fake_holdings)
        monkeypatch.setattr(portfolio_router, "get_stock_industries", fake_industries)

        resp = app_client.get(f"/api/portfolio/holdings?portfolio_id={pf_id}")
        assert resp.status_code == 200
        assert call_count["n"] == 1  # was 2 before compute_summary was shared
