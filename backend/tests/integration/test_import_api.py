"""CSV 导入编码/大小限制 & 批量导入空组合行为的集成测试。"""

import app.db as app_db
import app.routers.funds as funds_router
import app.services.fund_import as fund_import_svc
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


def _post_csv(client: TestClient, content: bytes):
    return client.post(
        "/api/transactions/csv",
        files={"file": ("tx.csv", content, "text/csv")},
    )


class TestCsvEncoding:
    def test_gbk_csv_imported(self, app_client):
        """国内 Excel 导出的 GBK 编码 CSV 应能正常解析（回退 gb18030）。"""
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        csv_text = (
            "code,direction,trade_date,nav,shares,fee,note\n"
            "110011,buy,2026-06-01,1.5,100,0,中文备注\n"
        )
        resp = _post_csv(app_client, csv_text.encode("gbk"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 1
        assert body["errors"] == []
        tx = app_client.get("/api/funds/110011/transactions").json()["items"][0]
        assert tx["note"] == "中文备注"

    def test_utf8_bom_csv_still_works(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        csv_text = (
            "code,direction,trade_date,nav,shares\n110011,buy,2026-06-01,1.5,100\n"
        )
        resp = _post_csv(app_client, csv_text.encode("utf-8-sig"))
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1

    def test_undecodable_csv_returns_400_not_500(self, app_client):
        """UTF-8 与 GB18030 都解不了的非法字节 → 400 中文提示。"""
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        resp = _post_csv(app_client, b"\xff\xff\xff not a csv \x81\x81")
        assert resp.status_code == 400
        assert "编码" in resp.json()["detail"]

    def test_oversize_csv_returns_400(self, app_client):
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        big = b"code,direction,trade_date,nav,shares\n" + b"1" * (2 * 1024 * 1024)
        resp = _post_csv(app_client, big)
        assert resp.status_code == 400
        assert "过大" in resp.json()["detail"]

    def test_csv_invalid_calendar_date_rejected(self, app_client):
        """非法日历日期（如 02-30）在路由层校验拦截，文案与手工录入统一。"""
        _add_fund(app_client)
        app_client.post("/api/portfolios", json={"name": "组合A"})
        csv_text = (
            "code,direction,trade_date,nav,shares\n110011,buy,2026-02-30,1.5,100\n"
        )
        resp = _post_csv(app_client, csv_text.encode())
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 0
        assert body["errors"] == ["line 2: trade_date 必须是有效的 YYYY-MM-DD 日期"]


class TestBatchImportPortfolio:
    def test_all_invalid_leaves_no_empty_portfolio(self, app_client, monkeypatch):
        """不带 portfolio_id 且全部基金解析失败 → 不创建空组合。"""

        async def broken_fetch_fund_info(code: str) -> dict:
            raise RuntimeError("数据源不可用")

        monkeypatch.setattr(fund_import_svc, "fetch_fund_info", broken_fetch_fund_info)

        resp = app_client.post(
            "/api/funds/batch", json={"codes": ["999999"], "funds": []}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == []
        assert "999999" in body["invalid"]
        assert body["portfolio_id"] is None
        with app_db.get_conn() as conn:
            assert not conn.execute("SELECT 1 FROM portfolios").fetchone()

    def test_successful_import_creates_portfolio(self, app_client):
        """有基金可导入时仍按原行为自动建组合。"""
        resp = app_client.post(
            "/api/funds/batch", json={"codes": ["110011"], "funds": []}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == ["110011"]
        assert body["portfolio_id"] is not None
        with app_db.get_conn() as conn:
            assert conn.execute("SELECT 1 FROM portfolios").fetchone()

    def test_import_with_invalid_nav_date_returns_400(self, app_client, monkeypatch):
        """上游返回非法日历日期：此前靠 tx_repo 兜底 500，现在路由层 400。"""

        async def fake_latest_nav(code: str) -> dict:
            return {"nav": "1.5", "date": "2026-02-30"}

        monkeypatch.setattr(fund_import_svc, "fetch_latest_nav", fake_latest_nav)

        resp = app_client.post(
            "/api/funds/batch",
            json={"codes": [], "funds": [{"code": "110011", "holding_amount": 1000}]},
        )
        assert resp.status_code == 400
        assert "净值日期无效" in resp.json()["detail"]
