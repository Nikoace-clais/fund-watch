"""Integration tests for the production backend (app/).

Uses an isolated temp SQLite DB and stubs out all external data-source
calls so tests run fully offline.
"""
import pytest
from fastapi.testclient import TestClient

import app.db as app_db
import app.routers.funds as funds_router
from app.main import app as fastapi_app


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """TestClient backed by a fresh temp DB; no lifespan (no scheduler)."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()

    async def fake_fetch_fund_info(code: str) -> dict:
        return {"name": f"测试基金{code}", "sector": "测试板块"}

    monkeypatch.setattr(funds_router, "fetch_fund_info", fake_fetch_fund_info)
    return TestClient(fastapi_app)


def _add_fund(client: TestClient, code: str = "110011") -> None:
    resp = client.post(f"/api/funds/{code}")
    assert resp.status_code == 200, resp.text


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
        resp = app_client.post("/api/funds/batch", json={"codes": ["badcode"], "funds": []})
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
        resp = app_client.post("/api/funds/110011/transactions", json={
            "direction": "buy", "trade_date": "2026-06-01",
            "nav": "1.5000", "shares": "1000", "fee": "1.5",
        })
        assert resp.status_code == 200
        pf_id = resp.json()["portfolio_id"]
        # holding_shares is now in positions table, not funds
        assert _get_position_shares("110011", pf_id) == "1000"

        txs = app_client.get("/api/funds/110011/transactions").json()["items"]
        assert len(txs) == 1
        assert txs[0]["amount"] == "1500.00"

    def test_sell_more_than_holding_rejected(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/funds/110011/transactions", json={
            "direction": "buy", "trade_date": "2026-06-01", "nav": "1.5", "shares": "100",
        })
        resp = app_client.post("/api/funds/110011/transactions", json={
            "direction": "sell", "trade_date": "2026-06-02", "nav": "1.6", "shares": "200",
        })
        assert resp.status_code == 400

    def test_transaction_for_missing_fund_404(self, app_client):
        resp = app_client.post("/api/funds/123456/transactions", json={
            "direction": "buy", "trade_date": "2026-06-01", "nav": "1.5", "shares": "100",
        })
        assert resp.status_code == 404

    def test_delete_transaction(self, app_client):
        _add_fund(app_client)
        buy_resp = app_client.post("/api/funds/110011/transactions", json={
            "direction": "buy", "trade_date": "2026-06-01", "nav": "1.5", "shares": "100",
        })
        pf_id = buy_resp.json()["portfolio_id"]
        tx_id = app_client.get("/api/funds/110011/transactions").json()["items"][0]["id"]
        resp = app_client.delete(f"/api/transactions/{tx_id}")
        assert resp.status_code == 200
        # After deletion, holding_shares should be NULL in positions
        assert _get_position_shares("110011", pf_id) is None

    def test_csv_import_with_dedup(self, app_client):
        _add_fund(app_client)
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


class TestDca:
    def _create_plan(self, client) -> int:
        resp = client.post("/api/dca/plans", json={
            "code": "110011", "amount": "500", "frequency": "weekly",
            "day_of_week": 1, "start_date": "2026-06-01",
        })
        assert resp.status_code == 200, resp.text
        return resp.json()["id"]

    def test_create_and_list_plan(self, app_client):
        plan_id = self._create_plan(app_client)
        items = app_client.get("/api/dca/plans").json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == plan_id
        assert items[0]["is_active"] == 1

    def test_create_plan_rejects_non_positive_amount(self, app_client):
        resp = app_client.post("/api/dca/plans", json={
            "code": "110011", "amount": "0", "frequency": "weekly", "start_date": "2026-06-01",
        })
        assert resp.status_code == 422

    def test_patch_plan(self, app_client):
        plan_id = self._create_plan(app_client)
        resp = app_client.patch(f"/api/dca/plans/{plan_id}", json={"amount": "800"})
        assert resp.status_code == 200
        assert app_client.get(f"/api/dca/plans/{plan_id}").json()["amount"] == "800"

    def test_records_and_stats(self, app_client):
        _add_fund(app_client)
        plan_id = self._create_plan(app_client)

        # success record requires a transaction
        app_client.post("/api/funds/110011/transactions", json={
            "direction": "buy", "trade_date": "2026-06-01", "nav": "1.25", "shares": "400",
        })
        tx_id = app_client.get("/api/funds/110011/transactions").json()["items"][0]["id"]
        r1 = app_client.post(f"/api/dca/plans/{plan_id}/records", json={
            "scheduled_date": "2026-06-01", "status": "success", "transaction_id": tx_id,
        })
        assert r1.status_code == 200
        r2 = app_client.post(f"/api/dca/plans/{plan_id}/records", json={
            "scheduled_date": "2026-06-08", "status": "failed", "note": "余额不足",
        })
        assert r2.status_code == 200

        records = app_client.get(f"/api/dca/plans/{plan_id}/records").json()["items"]
        assert len(records) == 2

        stats = app_client.get(f"/api/dca/plans/{plan_id}/stats").json()
        assert stats["total_periods"] == 2
        assert stats["success_count"] == 1
        assert stats["failed_count"] == 1
        assert stats["total_invested"] == "500.00"
        assert stats["total_shares"] == "400.0000"

        all_stats = app_client.get("/api/dca/stats").json()["items"]
        assert len(all_stats) == 1

    def test_success_record_requires_transaction(self, app_client):
        plan_id = self._create_plan(app_client)
        resp = app_client.post(f"/api/dca/plans/{plan_id}/records", json={
            "scheduled_date": "2026-06-01", "status": "success",
        })
        assert resp.status_code == 400

    def test_delete_plan_cascades_records(self, app_client):
        plan_id = self._create_plan(app_client)
        app_client.post(f"/api/dca/plans/{plan_id}/records", json={
            "scheduled_date": "2026-06-01", "status": "failed",
        })
        resp = app_client.delete(f"/api/dca/plans/{plan_id}")
        assert resp.status_code == 200
        assert app_client.get("/api/dca/plans").json()["items"] == []


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
