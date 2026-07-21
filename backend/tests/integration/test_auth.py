"""可选令牌鉴权（FUND_WATCH_TOKEN / X-Fund-Token）集成测试。

中间件每次请求读取环境变量，因此用 monkeypatch.setenv/delenv 即可
覆盖「设置 / 未设置」两种模式，无需重建 app。
"""

import app.db as app_db
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient

_TOKEN = "test-secret-token"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient backed by a fresh temp DB; token 状态由各用例自行控制。"""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    return TestClient(fastapi_app)


@pytest.fixture
def token_client(client, monkeypatch):
    monkeypatch.setenv("FUND_WATCH_TOKEN", _TOKEN)
    return client


class TestTokenUnset:
    """未设置 FUND_WATCH_TOKEN：行为与无鉴权完全一致。"""

    def test_api_without_header_ok(self, client, monkeypatch):
        monkeypatch.delenv("FUND_WATCH_TOKEN", raising=False)
        resp = client.get("/api/funds")
        assert resp.status_code == 200

    def test_health_ok(self, client, monkeypatch):
        monkeypatch.delenv("FUND_WATCH_TOKEN", raising=False)
        assert client.get("/api/health").status_code == 200


class TestTokenSet:
    """设置 FUND_WATCH_TOKEN：/api/* 须带 X-Fund-Token，/api/health 除外。"""

    def test_health_stays_public(self, token_client):
        assert token_client.get("/api/health").status_code == 200

    def test_missing_header_401(self, token_client):
        resp = token_client.get("/api/funds")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "未授权：缺少或无效的访问令牌"

    def test_wrong_token_401(self, token_client):
        resp = token_client.get("/api/funds", headers={"X-Fund-Token": "nope"})
        assert resp.status_code == 401

    def test_correct_token_ok(self, token_client):
        resp = token_client.get("/api/funds", headers={"X-Fund-Token": _TOKEN})
        assert resp.status_code == 200

    def test_sse_endpoint_also_protected(self, token_client):
        # 流式端点同样走中间件，缺头即 401（在进入路由/SSE 之前拦截）
        resp = token_client.post("/api/ocr/fund-code")
        assert resp.status_code == 401

    def test_options_preflight_not_blocked(self, token_client):
        # 浏览器预检不带自定义头，必须放行给 CORSMiddleware，
        # 且 X-Fund-Token 在允许头列表里（Vite dev server 跨域场景）
        resp = token_client.options(
            "/api/funds",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-fund-token",
            },
        )
        assert resp.status_code == 200
        assert "x-fund-token" in resp.headers["access-control-allow-headers"].lower()
