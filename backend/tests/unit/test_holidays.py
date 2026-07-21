"""holidays.is_trading_day 与 snapshots.in_trading_hours 的假日感知测试。"""

from __future__ import annotations

from datetime import date, datetime

from app.core import CST
from app.holidays import HOLIDAYS, is_trading_day
from app.services import snapshots


def test_2026_new_years_day_is_holiday() -> None:
    # 2026-01-01 是周四,元旦放假日 — 纯 weekday 判断会误判为交易日
    assert date(2026, 1, 1) in HOLIDAYS
    assert not is_trading_day(date(2026, 1, 1))


def test_plain_wednesday_is_trading_day() -> None:
    assert is_trading_day(date(2026, 3, 4))  # 普通周三


def test_weekend_is_not_trading_day() -> None:
    assert not is_trading_day(date(2026, 3, 7))  # 周六
    assert not is_trading_day(date(2026, 3, 8))  # 周日


def test_spring_festival_2026_is_not_trading_day() -> None:
    assert not is_trading_day(date(2026, 2, 17))  # 周二,春节假期(正月初一)


def test_in_trading_hours_skips_holiday(monkeypatch) -> None:
    # 2026-01-01 10:00 本在盘中窗口,但元旦休市,不应空拉
    class _FakeDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, 10, 0, tzinfo=CST)

    monkeypatch.setattr(snapshots, "datetime", _FakeDatetime)
    assert not snapshots.in_trading_hours()


def test_in_trading_hours_on_plain_trading_day(monkeypatch) -> None:
    class _FakeDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 4, 10, 0, tzinfo=CST)  # 周三盘中

    monkeypatch.setattr(snapshots, "datetime", _FakeDatetime)
    assert snapshots.in_trading_hours()
