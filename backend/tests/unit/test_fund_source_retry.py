"""_get_with_retry 对 HTTP 5xx 重试、4xx 不重试的测试(pytest-httpx)。"""

from __future__ import annotations

import asyncio as _asyncio

import httpx
import pytest
from app import fund_source

_URL = "https://example.com/api"


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch) -> None:
    """跳过重试退避等待(与 tests/integration/test_stocks_api.py 同款)。"""

    class _FastAsyncio:
        def __getattr__(self, name):
            return getattr(_asyncio, name)

        @staticmethod
        async def sleep(_delay):
            return None

    monkeypatch.setattr(fund_source, "asyncio", _FastAsyncio())


async def _get() -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await fund_source._get_with_retry(client, _URL)


async def test_retries_on_500_then_succeeds(httpx_mock) -> None:
    httpx_mock.add_response(status_code=500, text="server error")
    httpx_mock.add_response(status_code=200, json={"ok": True})

    resp = await _get()

    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 2


async def test_gives_up_after_max_retries_on_5xx(httpx_mock) -> None:
    for _ in range(3):
        httpx_mock.add_response(status_code=503, text="unavailable")

    with pytest.raises(httpx.HTTPStatusError):
        await _get()
    assert len(httpx_mock.get_requests()) == 3


async def test_does_not_retry_on_4xx(httpx_mock) -> None:
    httpx_mock.add_response(status_code=404, text="not found")

    with pytest.raises(httpx.HTTPStatusError):
        await _get()
    assert len(httpx_mock.get_requests()) == 1
