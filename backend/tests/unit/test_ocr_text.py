"""Unit tests for PaddleOCR + text AI OCR pipeline (AI model mocked)."""

from __future__ import annotations

import pytest
from app import ocr_service

_CFG = {"provider": "anthropic", "api_key": "test-key", "base_url": None, "model": None}


@pytest.mark.asyncio
async def test_extract_funds_happy(monkeypatch):
    async def _fake(text, prompt, **kw):
        return [{"code": "110011", "name": "易方达消费行业", "amount": 1234.56}]

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    result = await ocr_service.extract_funds_from_text("some ocr text", _CFG)
    assert result == [{"code": "110011", "name": "易方达消费行业", "amount": 1234.56}]


@pytest.mark.asyncio
async def test_extract_funds_filters_bad_codes(monkeypatch):
    async def _fake(text, prompt, **kw):
        return [
            {"code": "123"},  # too short → drop
            {"code": "abcdef"},  # not digits → drop
            {"code": "161725", "name": "招商中证白酒", "amount": None},
        ]

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    result = await ocr_service.extract_funds_from_text("ocr", _CFG)
    assert len(result) == 1
    assert result[0]["code"] == "161725"


@pytest.mark.asyncio
async def test_extract_funds_wrapped_object(monkeypatch):
    """json_object mode wraps array in {"funds": [...]}."""

    async def _fake(text, prompt, **kw):
        return {"funds": [{"code": "110011", "name": "易方达消费行业", "amount": None}]}

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    result = await ocr_service.extract_funds_from_text("ocr", _CFG)
    assert len(result) == 1
    assert result[0]["code"] == "110011"


@pytest.mark.asyncio
async def test_extract_funds_non_list(monkeypatch):
    async def _fake(text, prompt, **kw):
        return {}  # model returned empty object — no "funds" key

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    result = await ocr_service.extract_funds_from_text("ocr", _CFG)
    assert result == []


@pytest.mark.asyncio
async def test_extract_transaction(monkeypatch):
    async def _fake(text, prompt, **kw):
        return {
            "direction": "buy",
            "code": "012414",
            "trade_date": "2024-01-15",
            "nav": "1.2345",
            "shares": "1000.00",
            "amount": "1234.50",
        }

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    tx = await ocr_service.extract_transaction_from_text("ocr", _CFG)
    assert tx["direction"] == "buy"
    assert tx["code"] == "012414"
    assert tx["trade_date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_extract_transaction_null_fields(monkeypatch):
    async def _fake(text, prompt, **kw):
        return {
            "direction": None,
            "code": None,
            "trade_date": None,
            "nav": None,
            "shares": None,
            "amount": None,
        }

    monkeypatch.setattr(ocr_service, "_text_json", _fake)

    tx = await ocr_service.extract_transaction_from_text("ocr", _CFG)
    assert all(v is None for v in tx.values())


def test_parse_json_strips_fence():
    raw = "```json\n[1, 2, 3]\n```"
    assert ocr_service._parse_json(raw) == [1, 2, 3]


def test_parse_json_finds_array():
    raw = 'some text [{"code":"110011"}] trailing'
    result = ocr_service._parse_json(raw)
    assert result == [{"code": "110011"}]
