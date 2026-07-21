"""Integration tests for the production backend (app/).

Uses an isolated temp SQLite DB and stubs out all external data-source
calls so tests run fully offline.
"""

import app.db as app_db
import app.routers.funds as funds_router
import app.services.fund_import as fund_import_svc
import app.services.nav_history as nav_history_svc
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """TestClient backed by a fresh temp DB; no lifespan (no scheduler)."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()

    async def fake_fetch_fund_info(code: str) -> dict:
        return {"name": f"测试基金{code}", "sector": "测试板块"}

    monkeypatch.setattr(funds_router, "fetch_fund_info", fake_fetch_fund_info)
    monkeypatch.setattr(fund_import_svc, "fetch_fund_info", fake_fetch_fund_info)
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

    def test_search_upstream_failure_returns_generic_502(self, app_client, monkeypatch):
        """搜索上游失败 → 502 通用文案，内部异常细节不回传前端。"""

        async def broken_search(q: str, limit: int = 20) -> list:
            raise RuntimeError("connect http://internal-host:8080 refused")

        monkeypatch.setattr(funds_router, "search_fund_by_name", broken_search)

        resp = app_client.get("/api/funds/search?q=测试")
        assert resp.status_code == 502
        assert resp.json()["detail"] == "上游数据源请求失败，请稍后重试"

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
        app_client.post("/api/portfolios", json={"name": "组合A"})
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
        app_client.post("/api/portfolios", json={"name": "组合A"})
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

    def test_invalid_calendar_date_rejected(self, app_client):
        """非法日历日期（如 02-30）→ 400，文案与 CSV 路径统一。"""
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        resp = app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-02-30",
                "nav": "1.5",
                "shares": "100",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "trade_date 必须是有效的 YYYY-MM-DD 日期"

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
        app_client.post("/api/portfolios", json={"name": "组合A"})
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
        app_client.post("/api/portfolios", json={"name": "组合A"})
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


class TestTransactionChronology:
    def test_sell_dated_before_buy_rejected(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "buy",
                "trade_date": "2026-06-10",
                "nav": "1.5",
                "shares": "100",
            },
        )
        resp = app_client.post(
            "/api/funds/110011/transactions",
            json={
                "direction": "sell",
                "trade_date": "2026-06-01",
                "nav": "1.6",
                "shares": "50",
            },
        )
        assert resp.status_code == 400

    def test_delete_buy_that_breaks_chronology_rejected(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        for direction, date, shares in [
            ("buy", "2026-06-01", "100"),
            ("sell", "2026-06-05", "80"),
        ]:
            resp = app_client.post(
                "/api/funds/110011/transactions",
                json={
                    "direction": direction,
                    "trade_date": date,
                    "nav": "1.5",
                    "shares": shares,
                },
            )
            assert resp.status_code == 200

        txs = app_client.get("/api/funds/110011/transactions").json()["items"]
        buy_id = next(t["id"] for t in txs if t["direction"] == "buy")
        sell_id = next(t["id"] for t in txs if t["direction"] == "sell")

        # Deleting the buy would make the 06-05 sell dip below zero.
        assert app_client.delete(f"/api/transactions/{buy_id}").status_code == 400
        # Deleting the sell is always safe.
        assert app_client.delete(f"/api/transactions/{sell_id}").status_code == 200

    def test_csv_sell_dated_before_buy_rejected(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        csv_content = (
            "code,direction,trade_date,nav,shares,fee,note\n"
            "110011,buy,2026-06-10,1.5,100,0,\n"
            "110011,sell,2026-06-01,1.6,50,0,\n"
        )
        resp = app_client.post(
            "/api/transactions/csv",
            files={"file": ("tx.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 1
        assert len(body["errors"]) == 1
        assert "份额不足" in body["errors"][0]


class TestPortfolioSummary:
    def test_partial_sell_does_not_show_as_loss(self, app_client, monkeypatch):
        import asyncio

        import app.services.portfolio_service as ps

        _add_fund(app_client)
        pf_id = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        for direction, date, nav, shares in [
            ("buy", "2026-06-01", "1.0000", "1000"),
            ("sell", "2026-06-10", "1.5000", "400"),
        ]:
            resp = app_client.post(
                "/api/funds/110011/transactions",
                json={
                    "direction": direction,
                    "trade_date": date,
                    "nav": nav,
                    "shares": shares,
                },
            )
            assert resp.status_code == 200

        async def fake_quote(code: str) -> dict:
            return {"gsz": "1.5000", "gszzl": "0", "name": "测试基金110011"}

        monkeypatch.setattr(ps, "fetch_realtime_estimate", fake_quote)
        with app_db.get_conn() as conn:
            summary = asyncio.run(ps.compute_summary(conn, pf_id))

        item = next(i for i in summary["items"] if i["code"] == "110011")
        # Cost basis of the remaining 600 shares only (avg cost 1.0000).
        assert item["total_cost"] == "600.00"
        # realized 200 (400 sold at 1.5 over cost 1.0) + unrealized 300.
        assert item["realized_pnl"] == "200.00"
        assert item["total_return"] == "500.00"
        assert item["return_rate"] == "83.33"

    def test_fully_sold_position_stays_visible_with_realized_pnl(
        self, app_client, monkeypatch
    ):
        import asyncio

        import app.services.portfolio_service as ps

        _add_fund(app_client)
        pf_id = app_client.post("/api/portfolios", json={"name": "组合A"}).json()["id"]
        for direction, date, nav, shares in [
            ("buy", "2026-06-01", "1.0000", "1000"),
            ("sell", "2026-06-10", "1.5000", "400"),
            ("sell", "2026-06-20", "1.5000", "600"),
        ]:
            resp = app_client.post(
                "/api/funds/110011/transactions",
                json={
                    "direction": direction,
                    "trade_date": date,
                    "nav": nav,
                    "shares": shares,
                },
            )
            assert resp.status_code == 200

        async def fake_quote(code: str) -> dict:
            return {"gsz": "1.5000", "gszzl": "0", "name": "测试基金110011"}

        monkeypatch.setattr(ps, "fetch_realtime_estimate", fake_quote)
        with app_db.get_conn() as conn:
            summary = asyncio.run(ps.compute_summary(conn, pf_id))

        item = next(i for i in summary["items"] if i["code"] == "110011")
        assert item["is_closed"] is True
        assert item["current_value"] == "0.00"
        # 1500 proceeds - 1000 cost = 500 realized.
        assert item["total_return"] == "500.00"
        assert summary["total_return"] == "500.00"


class TestNavHistoryEndpoint:
    """nav-history 端点：改走 service（DB 优先）后响应形状保持不变。"""

    def test_response_shape_unchanged(self, app_client, monkeypatch):
        async def fake_history(code: str, limit: int = 365) -> list:
            return [
                {"date": "2026-07-20", "nav": 1.4, "accNav": 1.5, "dailyReturn": 0.1},
                {"date": "2026-07-21", "nav": 1.5, "accNav": 1.6, "dailyReturn": 0.2},
            ]

        monkeypatch.setattr(nav_history_svc, "fetch_nav_history", fake_history)

        resp = app_client.get("/api/funds/110011/nav-history?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "110011"
        assert body["count"] == 2
        assert body["history"] == [
            {"date": "2026-07-20", "nav": 1.4, "accNav": 1.5, "dailyReturn": 0.1},
            {"date": "2026-07-21", "nav": 1.5, "accNav": 1.6, "dailyReturn": 0.2},
        ]

        # 第二次请求 DB 已有数据，响应形状一致
        resp2 = app_client.get("/api/funds/110011/nav-history?limit=10")
        assert resp2.status_code == 200
        assert resp2.json()["count"] == 2

    def test_upstream_failure_returns_generic_502(self, app_client, monkeypatch):
        """DB 为空且上游失败 → 502 通用文案（与现状 fetch_502 模式一致）。"""

        async def broken(code: str, limit: int = 365) -> list:
            raise RuntimeError("connect http://internal-host:8080 refused")

        monkeypatch.setattr(nav_history_svc, "fetch_nav_history", broken)

        resp = app_client.get("/api/funds/110011/nav-history")
        assert resp.status_code == 502
        assert resp.json()["detail"] == "上游数据源请求失败，请稍后重试"

    def test_invalid_code_rejected(self, app_client):
        resp = app_client.get("/api/funds/abc/nav-history")
        assert resp.status_code == 400
