"""compute_summary 行情源失败时的降级展示(estimate_error)测试。"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

import httpx
import pytest
from app.services import portfolio_service


@pytest.fixture
def conn() -> sqlite3.Connection:
    """仓库层已全部打桩,连接只作占位满足签名。"""
    return sqlite3.connect(":memory:")


@pytest.fixture(autouse=True)
def _mock_repos(monkeypatch) -> None:
    """隔离 DB:持仓/交易/导入仓/观察仓全部打桩,conn 仅为占位。"""
    monkeypatch.setattr(
        portfolio_service.positions_repo,
        "list_holdings_with_shares",
        lambda conn, pf: [
            {"code": "110011", "name": "测试基金", "holding_shares": "100"}
        ],
    )
    monkeypatch.setattr(
        portfolio_service.tx_repo, "list_for_pnl_bulk", lambda conn, pf, codes: {}
    )
    monkeypatch.setattr(
        portfolio_service,
        "compute_pnl",
        lambda conn, pf, code, rows: {"realized_pnl": "0", "remaining_cost": "150"},
    )
    monkeypatch.setattr(
        portfolio_service.positions_repo,
        "list_imported_positions",
        lambda conn, pf: [],
    )
    monkeypatch.setattr(
        portfolio_service.positions_repo,
        "list_watch_only_codes",
        lambda conn, pf: [],
    )


async def test_estimate_failure_keeps_item_with_error_flag(monkeypatch, conn) -> None:
    """行情源异常:基金仍在列表中,估值字段为 None 且带 estimate_error。"""

    async def _boom(code):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(portfolio_service, "fetch_realtime_estimate", _boom)

    summary = await portfolio_service.compute_summary(conn, 1)

    assert summary["fund_count"] == 1
    item = summary["items"][0]
    assert item["code"] == "110011"
    assert item["estimate_error"] is True
    assert item["nav"] is None
    assert item["current_value"] is None
    assert item["daily_return"] is None
    assert item["total_return"] is None
    # 汇总统计对 None 值跳过(与旧行为一致:失败基金不参与任何汇总)
    assert Decimal(summary["total_current"]) == 0
    assert Decimal(summary["total_return"]) == 0


async def test_estimate_empty_gsz_keeps_item(monkeypatch, conn) -> None:
    """行情源返回但 gsz 为空:同样降级保留。"""

    async def _no_gsz(code):
        return {"name": "X", "gsz": None, "gszzl": None}

    monkeypatch.setattr(portfolio_service, "fetch_realtime_estimate", _no_gsz)

    summary = await portfolio_service.compute_summary(conn, 1)

    item = summary["items"][0]
    assert item["estimate_error"] is True
    assert item["nav"] is None


async def test_estimate_success_has_no_error_flag(monkeypatch, conn) -> None:
    """正常路径:不带 estimate_error,汇总数值不受影响。"""

    async def _ok(code):
        return {"name": "X", "gsz": 2.0, "gszzl": 1.0}

    monkeypatch.setattr(portfolio_service, "fetch_realtime_estimate", _ok)

    summary = await portfolio_service.compute_summary(conn, 1)

    item = summary["items"][0]
    assert "estimate_error" not in item
    assert item["current_value"] == "200.00"
    assert item["total_return"] == "50.00"  # 200.00 - 150(remaining_cost)
    assert Decimal(summary["total_current"]) == Decimal("200.00")
    assert Decimal(summary["total_return"]) == Decimal("50.00")
