"""Unit tests for P&L computation and transaction-log replay validation."""

from decimal import Decimal

import app.db as app_db
import pytest
from app.repositories import tx_repo
from app.services.holdings import compute_pnl, never_negative_when_replayed

PF = 1
CODE = "110011"


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Fresh temp DB; the transactions table alone is enough for this math."""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    with app_db.get_conn() as c:
        yield c


def _tx(conn, direction, trade_date, nav, shares, fee="0"):
    amount = str((Decimal(nav) * Decimal(shares)).quantize(Decimal("0.01")))
    tx_repo.insert(
        conn,
        code=CODE,
        portfolio_id=PF,
        direction=direction,
        trade_date=trade_date,
        nav=nav,
        shares=shares,
        amount=amount,
        fee=fee,
        note=None,
        source="test",
        created_at="2026-01-01T00:00:00+00:00",
    )


class TestComputePnl:
    def test_partial_sell_keeps_cost_of_remaining_shares_only(self, conn):
        _tx(conn, "buy", "2026-06-01", "1.0000", "1000", fee="10")
        _tx(conn, "sell", "2026-06-10", "1.2000", "400")
        _tx(conn, "buy", "2026-06-15", "1.1000", "500")

        # total cost 1560 over 1500 bought shares -> avg cost 1.0400
        pnl = compute_pnl(conn, PF, CODE, current_nav="1.3000")

        assert pnl["holding_shares"] == "1100"
        assert pnl["avg_cost_nav"] == "1.0400"
        # sold 400 @ avg 1.04 for 480 -> realized 64
        assert pnl["realized_pnl"] == "64.00"
        # remaining 1100 shares carry 1100 * 1.04 of cost basis, no more
        assert pnl["remaining_cost"] == "1144.00"
        assert pnl["unrealized_pnl"] == "286.00"
        assert pnl["total_pnl"] == "350.00"

    def test_fully_sold_position_reports_realized_pnl(self, conn):
        _tx(conn, "buy", "2026-06-01", "1.0000", "100")
        _tx(conn, "sell", "2026-06-10", "1.2000", "100")

        pnl = compute_pnl(conn, PF, CODE, current_nav="1.5000")

        assert pnl["holding_shares"] == "0"
        assert pnl["remaining_cost"] == "0.00"
        assert pnl["realized_pnl"] == "20.00"
        assert pnl["total_pnl"] == "20.00"


class TestReplayValidation:
    def test_sell_dated_before_buy_is_rejected(self, conn):
        _tx(conn, "buy", "2026-06-10", "1.0", "100")
        assert not never_negative_when_replayed(
            conn,
            PF,
            CODE,
            extra=[{"direction": "sell", "trade_date": "2026-06-01", "shares": "50"}],
        )

    def test_sell_after_buy_is_accepted(self, conn):
        _tx(conn, "buy", "2026-06-10", "1.0", "100")
        assert never_negative_when_replayed(
            conn,
            PF,
            CODE,
            extra=[{"direction": "sell", "trade_date": "2026-06-11", "shares": "50"}],
        )

    def test_sell_more_than_holding_is_rejected(self, conn):
        _tx(conn, "buy", "2026-06-10", "1.0", "100")
        assert not never_negative_when_replayed(
            conn,
            PF,
            CODE,
            extra=[{"direction": "sell", "trade_date": "2026-06-11", "shares": "150"}],
        )

    def test_same_day_sell_after_buy_is_accepted(self, conn):
        _tx(conn, "buy", "2026-06-10", "1.0", "100")
        assert never_negative_when_replayed(
            conn,
            PF,
            CODE,
            extra=[{"direction": "sell", "trade_date": "2026-06-10", "shares": "100"}],
        )

    def test_remove_id_replays_without_that_row(self, conn):
        _tx(conn, "buy", "2026-06-01", "1.0", "100")
        _tx(conn, "buy", "2026-06-05", "1.0", "100")
        _tx(conn, "sell", "2026-06-10", "1.2", "150")
        rows = tx_repo.list_by_code(conn, PF, CODE)
        ids = {r["direction"] + r["trade_date"]: r["id"] for r in rows}

        # Removing either buy makes the 06-10 sell dip below zero.
        assert not never_negative_when_replayed(
            conn, PF, CODE, remove_id=ids["buy2026-06-01"]
        )
        assert not never_negative_when_replayed(
            conn, PF, CODE, remove_id=ids["buy2026-06-05"]
        )
        # Removing the sell is always safe.
        assert never_negative_when_replayed(
            conn, PF, CODE, remove_id=ids["sell2026-06-10"]
        )
