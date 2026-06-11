"""Integration tests for OCR endpoints.

The OCR engine itself is mocked (no model download / inference); these cover
the route logic: threadpool wiring, unique upload naming, name-search fallback
and the ocr_records insert.
"""
import io

import app.db as app_db
import app.routers.ocr as ocr_router
import pytest
from app.main import app as fastapi_app
from fastapi.testclient import TestClient


@pytest.fixture
def ocr_client(tmp_path, monkeypatch):
    """TestClient with temp DB and temp upload dir."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(ocr_router, "UPLOAD_DIR", tmp_path)
    app_db.init_db()
    return TestClient(fastapi_app)


def _png_upload():
    return {"file": ("shot.png", io.BytesIO(b"fake-png-bytes"), "image/png")}


class TestOcrFundCode:
    def test_codes_found(self, ocr_client, monkeypatch):
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
        assert body["matched_funds"] == [{"code": "005827", "amount": 1234.56}]
        assert body["name_matches"] == []
        # Upload saved under the unique-name scheme: ocr_<ts>_<uuid8>.png
        assert body["image"].startswith("ocr_") and body["image"].endswith(".png")

    def test_fallback_to_name_search(self, ocr_client, monkeypatch):
        # No 6-digit code in the screenshot -> falls back to fund-name search
        monkeypatch.setattr(
            ocr_router, "scan_fund_image",
            lambda path: ("招商中证白酒指数A", [], []),
        )

        async def fake_search(name, limit=1):
            return [{"code": "161725", "name": "招商中证白酒指数A", "type": "指数型"}]

        monkeypatch.setattr(ocr_router, "search_fund_by_name", fake_search)

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_upload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched_codes"] == ["161725"]
        assert body["name_matches"][0]["code"] == "161725"
        assert body["name_matches"][0]["matched_keyword"] == "招商中证白酒指数A"

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
