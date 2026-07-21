"""Integration tests for OCR endpoints.

The OCR engine and the AI extraction/review calls are mocked (no model
download / inference, no network); these cover the route logic: threadpool
wiring, unique upload naming, code verification against the fund source,
name-search fallback merge and the ocr_records insert.

/api/ocr/fund-code streams SSE events (step/error/result); tests parse the
final `result` event's payload.
"""

import io
import json
import os
import time

import app.db as app_db
import app.routers.ocr as ocr_endpoints
import app.services.ocr_pipeline as ocr_router  # noqa: N813 — pipeline moved out of the router
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
    """TestClient with temp DB, temp upload dir, and OCR text extraction stubbed."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(ocr_router, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(ocr_router, "ocr_text", lambda path: "raw ocr text")
    app_db.init_db()
    return TestClient(fastapi_app)


@pytest.fixture
def fake_search(monkeypatch):
    """search_fund_by_name stub: looks up by exact code or name substring."""

    async def _search(q, limit=1):
        hits = [
            f
            for f in _FUNDS.values()
            if f["code"] == q or q in f["name"] or f["name"] in q
        ]
        return hits[:limit]

    monkeypatch.setattr(ocr_router, "search_fund_by_name", _search)
    return _search


def _fund_ai(funds):
    """Build an extract_funds_from_text stub returning a fixed [{code,name,amount}]."""

    async def _extract(text, cfg):
        return funds

    return _extract


def _png_files(field: str):
    return {field: ("shot.png", io.BytesIO(b"fake-png-bytes"), "image/png")}


def _sse_result(resp) -> dict:
    """Extract the final `result` event's data payload from an SSE response."""
    for line in resp.text.splitlines():
        if not line.startswith("data: "):
            continue
        evt = json.loads(line[len("data: ") :])
        if evt["type"] == "error":
            raise AssertionError(f"pipeline error: {evt.get('text')}")
        if evt["type"] == "result":
            return evt["data"]
    raise AssertionError("no result event in SSE stream")


class TestOcrFundCode:
    def test_codes_found_and_verified(self, ocr_client, fake_search, monkeypatch):
        monkeypatch.setattr(
            ocr_router,
            "extract_funds_from_text",
            _fund_ai([{"code": "005827", "name": "", "amount": 1234.56}]),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        assert resp.status_code == 200
        body = _sse_result(resp)
        assert body["matched_codes"] == ["005827"]
        # Verification enriches matched_funds with the source name
        assert body["matched_funds"] == [
            {"code": "005827", "name": "易方达蓝筹精选混合", "amount": 1234.56}
        ]
        # Name in screenshot maps back to the same fund -> no duplicate
        assert body["name_matches"] == []

    def test_false_positive_code_dropped(self, ocr_client, fake_search, monkeypatch):
        # 100056 is an amount fragment, not a fund; source doesn't know it
        monkeypatch.setattr(
            ocr_router,
            "extract_funds_from_text",
            _fund_ai([{"code": "100056", "name": "", "amount": None}]),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        body = _sse_result(resp)
        assert body["matched_codes"] == []
        assert body["matched_funds"] == []

    def test_source_down_keeps_candidate(self, ocr_client, monkeypatch):
        monkeypatch.setattr(
            ocr_router,
            "extract_funds_from_text",
            _fund_ai([{"code": "005827", "name": "", "amount": None}]),
        )

        async def broken_search(q, limit=1):
            raise RuntimeError("source down")

        monkeypatch.setattr(ocr_router, "search_fund_by_name", broken_search)

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        body = _sse_result(resp)
        # Can't verify -> keep the candidate instead of losing recall
        assert body["matched_codes"] == ["005827"]

    def test_name_fallback_when_no_codes(self, ocr_client, fake_search, monkeypatch):
        monkeypatch.setattr(
            ocr_router,
            "extract_funds_from_text",
            _fund_ai([{"code": "", "name": "招商中证白酒指数A", "amount": None}]),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        body = _sse_result(resp)
        assert body["matched_codes"] == ["161725"]
        assert body["name_matches"][0]["code"] == "161725"
        assert body["name_matches"][0]["ocr_name"] == "招商中证白酒指数A"

    def test_name_fallback_merges_with_codes(
        self,
        ocr_client,
        fake_search,
        monkeypatch,
    ):
        # One fund recognized by code, another only by name -> both returned
        monkeypatch.setattr(
            ocr_router,
            "extract_funds_from_text",
            _fund_ai(
                [
                    {"code": "005827", "name": "易方达蓝筹精选混合", "amount": 2000.0},
                    {"code": "", "name": "招商中证白酒指数A", "amount": None},
                ]
            ),
        )

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        body = _sse_result(resp)
        assert body["matched_codes"] == ["005827", "161725"]
        assert [m["code"] for m in body["name_matches"]] == ["161725"]

    def test_unique_filenames_for_concurrent_uploads(
        self,
        ocr_client,
        monkeypatch,
        tmp_path,
    ):
        seen_paths = []

        def _spy_ocr(path):
            seen_paths.append(path)
            return "raw ocr text"

        monkeypatch.setattr(ocr_router, "ocr_text", _spy_ocr)
        monkeypatch.setattr(ocr_router, "extract_funds_from_text", _fund_ai([]))
        for _ in range(5):
            resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
            assert resp.status_code == 200
        # Each upload gets a unique on-disk name under the unique-name scheme
        # (ocr_<ts>_<uuid8>.png), even though the original filename is reused.
        names = [p.name for p in seen_paths]
        assert len(set(names)) == 5
        assert all(n.startswith("ocr_") and n.endswith(".png") for n in names)
        # 处理完成后临时文件已被清理
        assert list(tmp_path.glob("ocr_*.png")) == []


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

        async def _extract(text, cfg):
            return tx

        monkeypatch.setattr(ocr_endpoints, "extract_transaction_from_text", _extract)

        resp = ocr_client.post("/api/ocr/transaction", files=_png_files("file"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction"] == tx
        assert body["image"].startswith("ocr_tx_")

    def test_upload_deleted_after_processing(self, ocr_client, monkeypatch, tmp_path):
        async def _extract(text, cfg):
            return {"direction": "buy", "code": "005827"}

        monkeypatch.setattr(ocr_endpoints, "extract_transaction_from_text", _extract)

        resp = ocr_client.post("/api/ocr/transaction", files=_png_files("file"))
        assert resp.status_code == 200
        # 处理完成后临时文件已被清理
        assert list(tmp_path.glob("ocr_tx_*")) == []


class TestUploadValidation:
    def test_bad_extension_rejected(self, ocr_client):
        resp = ocr_client.post(
            "/api/ocr/transaction",
            files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "类型" in resp.json()["detail"]

    def test_oversize_file_rejected(self, ocr_client):
        big = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))
        resp = ocr_client.post(
            "/api/ocr/transaction",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 400
        assert "过大" in resp.json()["detail"]

    def test_fund_code_bad_extension_rejected(self, ocr_client):
        resp = ocr_client.post(
            "/api/ocr/fund-code",
            files={"files": ("a.gif", io.BytesIO(b"x"), "image/gif")},
        )
        assert resp.status_code == 400
        assert "类型" in resp.json()["detail"]


class TestOcrFailureHandling:
    def test_transaction_ocr_failure_returns_400(
        self, ocr_client, monkeypatch, tmp_path
    ):
        """非图片内容让 OCR 引擎抛异常 → 400 中文提示，且临时文件被清理。"""

        def _boom(path):
            raise RuntimeError("not an image")

        monkeypatch.setattr(ocr_router, "ocr_text", _boom)

        resp = ocr_client.post("/api/ocr/transaction", files=_png_files("file"))
        assert resp.status_code == 400
        assert "识别失败" in resp.json()["detail"]
        assert list(tmp_path.glob("ocr_tx_*")) == []

    def test_fund_code_ocr_failure_yields_error_event(
        self, ocr_client, monkeypatch, tmp_path
    ):
        """SSE 流式端点无法中途改状态码 → error 事件，且临时文件被清理。"""

        def _boom(path):
            raise RuntimeError("not an image")

        monkeypatch.setattr(ocr_router, "ocr_text", _boom)

        resp = ocr_client.post("/api/ocr/fund-code", files=_png_files("files"))
        assert resp.status_code == 200
        events = [
            json.loads(line[len("data: ") :])
            for line in resp.text.splitlines()
            if line.startswith("data: ")
        ]
        assert any(
            e["type"] == "error" and "识别失败" in e["text"] for e in events
        )
        assert list(tmp_path.glob("ocr_*.png")) == []


def test_cleanup_stale_uploads(tmp_path, monkeypatch):
    """启动清理：mtime 超过 24h 的残留文件被删除，新文件保留。"""
    monkeypatch.setattr(ocr_router, "UPLOAD_DIR", tmp_path)
    old = tmp_path / "ocr_old.png"
    old.write_bytes(b"x")
    new = tmp_path / "ocr_new.png"
    new.write_bytes(b"x")
    old_mtime = time.time() - 25 * 3600
    os.utime(old, (old_mtime, old_mtime))

    assert ocr_router.cleanup_stale_uploads() == 1
    assert not old.exists()
    assert new.exists()
