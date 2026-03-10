from __future__ import annotations

from unittest.mock import AsyncMock, patch


def test_add_fund_and_patch_amount(client):
    with patch("app.main.fetch_fund_info", new=AsyncMock(return_value={"name": "Test Fund", "sector": "白酒"})):
        r = client.post("/api/funds/161725", json={"amount": 1000})
    assert r.status_code == 200

    r2 = client.patch("/api/funds/161725", json={"amount": 1200})
    assert r2.status_code == 200

    funds = client.get("/api/funds/overview").json()["items"]
    row = next(x for x in funds if x["fund"]["code"] == "161725")
    assert row["fund"]["amount"] == 1200


def test_batch_add_funds_with_invalid_codes(client):
    with patch("app.main.fetch_fund_info", new=AsyncMock(return_value={"name": "Any", "sector": "消费"})):
        r = client.post(
            "/api/funds/batch",
            json={"codes": ["161725", "abc", "005827", "12345", "005827"]},
        )

    assert r.status_code == 200
    body = r.json()
    assert sorted(body["added"]) == ["005827", "161725"]
    assert sorted(body["invalid"]) == ["12345", "abc"]


def test_pnl_returns_backward_compatible_alias_fields(client):
    with patch("app.main.fetch_fund_info", new=AsyncMock(return_value={"name": "Test", "sector": "白酒"})):
        client.post("/api/funds/161725")

    r = client.post(
        "/api/funds/161725/transactions",
        json={
            "direction": "buy",
            "trade_date": "2026-03-01",
            "nav": "1.0000",
            "shares": "1000",
            "fee": "0",
        },
    )
    assert r.status_code == 200

    with patch(
        "app.main.fetch_realtime_estimate",
        new=AsyncMock(
            return_value={
                "fundcode": "161725",
                "name": "Test",
                "dwjz": 1.0,
                "gsz": 1.1,
                "gszzl": 10.0,
                "gztime": "2026-03-03 09:30",
            }
        ),
    ):
        pnl = client.get("/api/funds/161725/pnl")

    assert pnl.status_code == 200
    data = pnl.json()
    assert data["has_transactions"] is True
    assert "total_pnl" in data
    assert "total_pnl_rate" in data
    assert "pnl" in data
    assert "pnl_rate" in data
