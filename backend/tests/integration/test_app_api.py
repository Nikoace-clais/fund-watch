"""Integration tests for the production backend (app/).

Uses an isolated temp SQLite DB and stubs out all external data-source
calls so tests run fully offline.
"""

import app.db as app_db
import app.main as app_main
import app.routers.funds as funds_router
import pytest
from app.main import app as fastapi_app

from tests.client import ASGISyncClient


@pytest.mark.asyncio
async def test_lifespan_test_mode_skips_ocr_and_scheduler(monkeypatch, tmp_path):
    monkeypatch.setenv("FUND_WATCH_TEST_MODE", "1")
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(app_main, "init_db", lambda: None)
    monkeypatch.setattr(app_main, "UPLOAD_DIR", tmp_path / "uploads")

    def fail_warm_up() -> None:
        raise AssertionError("OCR warm-up should be disabled in test mode")

    def fail_create_task(_coro):
        raise AssertionError("snapshot scheduler should be disabled in test mode")

    async def fake_close() -> None:
        return None

    monkeypatch.setattr(app_main, "warm_up_ocr", fail_warm_up)
    monkeypatch.setattr(app_main.asyncio, "create_task", fail_create_task)
    monkeypatch.setattr(app_main, "close_shared_client", fake_close)

    async with app_main.lifespan(app_main.app):
        pass


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """TestClient backed by a fresh temp DB; no lifespan (no scheduler)."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()

    async def fake_fetch_fund_info(code: str) -> dict:
        return {"name": f"测试基金{code}", "sector": "测试板块"}

    monkeypatch.setattr(funds_router, "fetch_fund_info", fake_fetch_fund_info)
    return ASGISyncClient(fastapi_app)


def _add_fund(client: ASGISyncClient, code: str = "110011") -> None:
    resp = client.post(f"/api/funds/{code}")
    assert resp.status_code == 200, resp.text


def _create_portfolio(client: ASGISyncClient, name: str = "组合A") -> int:
    resp = client.post("/api/portfolios", json={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestHealth:
    def test_health(self, app_client):
        resp = app_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestFunds:
    def test_add_and_list_fund(self, app_client):
        _add_fund(app_client, "110011")
        resp = app_client.get("/api/funds")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["code"] == "110011"
        assert items[0]["name"] == "测试基金110011"

    def test_add_fund_rejects_invalid_code(self, app_client):
        resp = app_client.post("/api/funds/abc123")
        assert resp.status_code == 400

    def test_batch_route_not_shadowed_by_code_route(self, app_client):
        # "batch" must hit the batch endpoint, not be parsed as a fund code
        resp = app_client.post(
            "/api/funds/batch", json={"codes": ["badcode"], "funds": []}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "badcode" in body["invalid"]

    def test_delete_fund(self, app_client):
        _add_fund(app_client, "110011")
        resp = app_client.delete("/api/funds/110011")
        assert resp.status_code == 200
        assert app_client.get("/api/funds").json()["items"] == []

    def test_delete_missing_fund_404(self, app_client):
        resp = app_client.delete("/api/funds/999999")
        assert resp.status_code == 404

    def test_delete_fund_from_portfolio_keeps_global_fund_and_other_positions(
        self, app_client
    ):
        _add_fund(app_client, "110011")
        pf1 = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        pf2 = app_client.post("/api/portfolios", json={"name": "组合B"}).json()["id"]
        for pf in (pf1, pf2):
            resp = app_client.post(
                "/api/funds/batch",
                json={"codes": ["110011"], "portfolio_id": pf},
            )
            assert resp.status_code == 200

        resp = app_client.delete(f"/api/funds/110011?portfolio_id={pf1}")
        assert resp.status_code == 200
        assert resp.json()["scope"] == "portfolio"

        with app_db.get_conn() as conn:
            assert conn.execute(
                "SELECT 1 FROM funds WHERE code=?", ("110011",)
            ).fetchone()
            assert not conn.execute(
                "SELECT 1 FROM positions WHERE portfolio_id=? AND code=?",
                (pf1, "110011"),
            ).fetchone()
            assert conn.execute(
                "SELECT 1 FROM positions WHERE portfolio_id=? AND code=?",
                (pf2, "110011"),
            ).fetchone()


def _get_position_shares(code: str, portfolio_id: int) -> str | None:
    """Helper: read holding_shares directly from positions table."""
    import app.db as _db

    with _db.get_conn() as conn:
        row = conn.execute(
            "SELECT holding_shares FROM positions WHERE portfolio_id=? AND code=?",
            (portfolio_id, code),
        ).fetchone()
    return row["holding_shares"] if row else None


class TestTransactions:
    def test_buy_recomputes_holding_shares(self, app_client):
        _add_fund(app_client)
        _create_portfolio(app_client)
        resp = app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5000",
                "shares": "1000",
                "fee": "1.5",
            },
        )
        assert resp.status_code == 200
        pf_id = resp.json()["portfolio_id"]
        # holding_shares is now in positions table, not funds
        assert _get_position_shares("110011", pf_id) == "1000"

        txs = app_client.get("/api/funds/110011/transactions").json()["items"]
        assert len(txs) == 1
        assert txs[0]["amount"] == "1500.00"

    def test_sell_more_than_holding_rejected(self, app_client):
        _add_fund(app_client)
        _create_portfolio(app_client)
        app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5",
                "shares": "100",
            },
        )
        resp = app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "sell",
                "trade_date": "2026-06-02",
                "nav": "1.6",
                "shares": "200",
            },
        )
        assert resp.status_code == 400

    def test_transaction_for_missing_fund_404(self, app_client):
        resp = app_client.post(
            "/api/funds/123456/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5",
                "shares": "100",
            },
        )
        assert resp.status_code == 404

    def test_delete_transaction(self, app_client):
        _add_fund(app_client)
        _create_portfolio(app_client)
        buy_resp = app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-01",
                "nav": "1.5",
                "shares": "100",
            },
        )
        pf_id = buy_resp.json()["portfolio_id"]
        tx_id = app_client.get("/api/funds/110011/transactions").json()["items"][0][
            "id"
        ]
        resp = app_client.delete(f"/api/transactions/{tx_id}")
        assert resp.status_code == 200
        # After deletion, holding_shares should be NULL in positions
        assert _get_position_shares("110011", pf_id) is None

    def test_csv_import_with_dedup(self, app_client):
        _add_fund(app_client)
        _create_portfolio(app_client)
        csv_content = (
            "code,direction,trade_date,nav,shares,fee,note\n"
            "110011,buy,2026-06-01,1.5,100,0,first\n"
            "110011,buy,2026-06-01,1.5,100,0,duplicate\n"
            "bad,buy,2026-06-01,1.5,100,0,invalid-code\n"
        )
        resp = app_client.post(
            "/api/transactions/csv",
            files={"file": ("tx.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 1
        assert body["skipped"] == 1
        assert len(body["errors"]) == 1

    def test_transactions_are_scoped_by_portfolio(self, app_client):
        _add_fund(app_client)
        pf1 = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        pf2 = app_client.post("/api/portfolios", json={"name": "组合B"}).json()["id"]

        for pf_id, shares in [(pf1, "100"), (pf2, "200")]:
            resp = app_client.post(
                "/api/funds/110011/transactions",
                json={
                    "direction": "buy",
                    "trade_date": "2026-06-01",
                    "nav": "1.5",
                    "shares": shares,
                    "portfolio_id": pf_id,
                },
            )
            assert resp.status_code == 200

        txs1 = app_client.get(
            f"/api/funds/110011/transactions?portfolio_id={pf1}"
        ).json()["items"]
        txs2 = app_client.get(
            f"/api/funds/110011/transactions?portfolio_id={pf2}"
        ).json()["items"]

        assert [tx["shares"] for tx in txs1] == ["100"]
        assert [tx["shares"] for tx in txs2] == ["200"]


class TestSnapshots:
    def test_snapshots_empty(self, app_client):
        resp = app_client.get("/api/snapshots/110011?limit=5")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_cron_status_shape(self, app_client):
        body = app_client.get("/api/cron/status").json()
        assert body["interval_minutes"] == 5
        assert "pull_count" in body
        assert "is_active" in body
