"""Integration tests for OCR endpoints.

The OCR engine itself is mocked (no model download / inference); these cover
the route logic: threadpool wiring, unique upload naming, code verification
against the fund source, name-search fallback merge and the ocr_records insert.
"""
import io

import app.db as app_db
import app.routers.ocr as ocr_router
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient

# Minimal fund universe the fake search source knows about
_FUNDS = {
    "005827": {"code": "005827", "name": "易方达蓝筹精选混合", "type": "混合型"},
    "161725": {"code": "161725", "name": "招商中证白酒指数A", "type": "指数型"},
}


@pytest.fixture
def ocr_client(tmp_path, monkeypatch):
    """TestClient with temp DB and temp upload dir."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(ocr_router, "UPLOAD_DIR", tmp_path)
    app_db.init_db()
    return TestClient(fastapi_app)


@pytest.fixture
def fake_search(monkeypatch):
    """search_fund_by_name stub: looks up by exact code or name substring."""

    async def _search(q, limit=1):
        hits = [
            f for f in _FUNDS.values()
            if f["code"] == q or q in f["name"] or f["name"] in q
        ]
        return hits[:limit]

    monkeypatch.setattr(ocr_router, "search_fund_by_name", _search)
    return _search


def _png_upload():
    return {"file": ("shot.png", io.BytesIO(b"fake-png-bytes"), "image/png")}


class TestOcrFundCode:
    def test_codes_found_and_verified(self, ocr_client, fake_search, monkeypatch):
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: (
                "易方达蓝筹精选混合\n005827",
                ["005827"],
                [{"code": "005827", "amount": 1234.56}],
            ),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched_codes"] == ["005827"]
        # Verification enriches matched_funds with the source name
        assert body["matched_funds"] == [
            {"code": "005827", "name": "易方达蓝筹精选混合", "amount": 1234.56}
        ]
        # Name in screenshot maps back to the same fund -> no duplicate
        assert body["name_matches"] == []
        # Upload saved under the unique-name scheme: ocr_<ts>_<uuid8>.png
        assert body["image"].startswith("ocr_") and body["image"].endswith(".png")

    def test_false_positive_code_dropped(self, ocr_client, fake_search, monkeypatch):
        # 100056 is an amount fragment, not a fund; source doesn't know it
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: (
                "持有金额100056元",
                ["100056"],
                [{"code": "100056", "amount": None}],
            ),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        body = resp.json()
        assert body["matched_codes"] == []
        assert body["matched_funds"] == []

    def test_source_down_keeps_candidate(self, ocr_client, monkeypatch):
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: ("005827", ["005827"], [{"code": "005827", "amount": None}]),
        )

        async def broken_search(q, limit=1):
            raise RuntimeError("source down")

        monkeypatch.setattr(ocr_router, "search_fund_by_name", broken_search)

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        body = resp.json()
        # Can't verify -> keep the candidate instead of losing recall
        assert body["matched_codes"] == ["005827"]

    def test_name_fallback_when_no_codes(self, ocr_client, fake_search, monkeypatch):
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: ("招商中证白酒指数A", [], []),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        body = resp.json()
        assert body["matched_codes"] == ["161725"]
        assert body["name_matches"][0]["code"] == "161725"
        assert body["name_matches"][0]["matched_keyword"] == "招商中证白酒指数A"

    def test_name_fallback_merges_with_codes(
        self, ocr_client, fake_search, monkeypatch,
    ):
        # One fund recognized by code, another only by name -> both returned
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: (
                "易方达蓝筹精选混合\n005827\n招商中证白酒指数A",
                ["005827"],
                [{"code": "005827", "amount": 2000.0}],
            ),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        body = resp.json()
        assert body["matched_codes"] == ["005827", "161725"]
        assert [m["code"] for m in body["name_matches"]] == ["161725"]

    def test_unique_filenames_for_concurrent_uploads(self, ocr_client, monkeypatch):
        monkeypatch.setattr(
            ocr_router, "scan_fund_image", lambda path: ("", [], []),
        )
        names = set()
        for _ in range(5):
            resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
            names.add(resp.json()["image"])
        assert len(names) == 5


class TestOcrTransaction:
    def test_transaction_extracted(self, ocr_client, monkeypatch):
        tx = {
            "direction": "buy",
            "code": "005827",
            "trade_date": "2026-06-10",
            "nav": "2.5000",
            "shares": "400.00",
            "amount": "1000.00",
        }
        monkeypatch.setattr(
            ocr_router, "extract_transaction_from_image",
            lambda path: ("买入 005827 确认份额400.00", tx),
        )

        resp = ocr_client.post("/api/ocr/transaction", files=_png_upload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction"] == tx
        assert body["image"].startswith("ocr_tx_")
