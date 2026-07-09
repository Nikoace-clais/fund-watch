"""Tests for the shared pingzhongdata cache and TTLCache eviction (PR2)."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app import fund_source


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None, None, None]:
    fund_source._pingzhong_cache.clear()
    fund_source._nav_history_cache.clear()
    yield
    fund_source._pingzhong_cache.clear()
    fund_source._nav_history_cache.clear()


def _mock_client(text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.text = text
    client = AsyncMock()
    client.get.return_value = resp
    return client


@pytest.mark.asyncio
async def test_fund_info_and_detail_share_one_download() -> None:
    """fetch_fund_info + fetch_fund_detail for the same code hit the network once."""
    text = 'var fS_name = "招商中证白酒指数(LOF)A";var fS_code = "161725";'
    client = _mock_client(text)

    with patch("app.fund_source._get_client", return_value=client):
        info = await fund_source.fetch_fund_info("161725")
        detail = await fund_source.fetch_fund_detail("161725")

    assert client.get.call_count == 1  # second call served from _pingzhong_cache
    assert info["name"] == "招商中证白酒指数(LOF)A"
    assert detail["name"] == "招商中证白酒指数(LOF)A"


@pytest.mark.asyncio
async def test_pingzhong_cache_is_bounded() -> None:
    """TTLCache evicts past maxsize — a plain dict would grow unbounded instead."""
    assert fund_source._pingzhong_cache.maxsize == 200
