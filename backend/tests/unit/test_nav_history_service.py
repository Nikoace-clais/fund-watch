"""services.nav_history 单元测试：DB 优先读取、收盘后增量刷新、上游落库。

统一把「现在」钉在 2026-07-21（周二，交易日）16:00 CST —— 已过 15:30
净值发布时点，latest_date 落后于今天就应触发增量刷新。
"""

from __future__ import annotations

from datetime import datetime

import app.db as app_db
import pytest
from app.core import CST
from app.repositories import nav_history_repo
from app.services import nav_history as nav_history_svc

_NOW = datetime(2026, 7, 21, 16, 0, tzinfo=CST)


class _FakeDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return _NOW if tz is None else _NOW.astimezone(tz)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    monkeypatch.setattr(nav_history_svc, "datetime", _FakeDatetime)
    with app_db.get_conn() as c:
        yield c


def _rows(*items):
    """构造 fetch_nav_history 返回形状的行：(date, nav, accNav)。"""
    return [
        {"date": d, "nav": n, "accNav": a, "dailyReturn": None} for d, n, a in items
    ]


async def test_db_has_today_data_skips_upstream(conn, monkeypatch):
    """DB 已有今日数据：不拉上游，直接读库返回。"""
    nav_history_repo.upsert_many(conn, "110011", _rows(("2026-07-21", 1.5, 1.6)))

    async def _boom(code, limit=365):
        raise AssertionError("不应请求上游")

    monkeypatch.setattr(nav_history_svc, "fetch_nav_history", _boom)

    out = await nav_history_svc.get_nav_history(conn, "110011", 365)
    assert out == [
        {"date": "2026-07-21", "nav": 1.5, "accNav": 1.6, "dailyReturn": None}
    ]


async def test_empty_db_pulls_upstream_and_persists(conn, monkeypatch):
    """DB 为空：拉上游全量并落库，之后读库返回。"""
    rows = _rows(("2026-07-20", 1.4, 1.5), ("2026-07-21", 1.5, 1.6))

    async def _fake(code, limit=365):
        return rows

    monkeypatch.setattr(nav_history_svc, "fetch_nav_history", _fake)

    out = await nav_history_svc.get_nav_history(conn, "110011", 365)
    assert [r["date"] for r in out] == ["2026-07-20", "2026-07-21"]
    # 落库成功：增量锚点更新为最新交易日
    assert nav_history_repo.latest_date(conn, "110011") == "2026-07-21"


async def test_stale_db_incremental_refresh_adds_new_dates(conn, monkeypatch):
    """DB 落后于今天且已过 15:30：增量刷新只补新日期，旧值不变。"""
    nav_history_repo.upsert_many(conn, "110011", _rows(("2026-07-20", 1.4, 1.5)))

    calls = []

    async def _fake(code, limit=365):
        calls.append(code)
        return _rows(("2026-07-20", 1.4, 1.5), ("2026-07-21", 1.5, 1.6))

    monkeypatch.setattr(nav_history_svc, "fetch_nav_history", _fake)

    out = await nav_history_svc.get_nav_history(conn, "110011", 365)
    assert calls == ["110011"]  # 上游只拉一次
    assert [r["date"] for r in out] == ["2026-07-20", "2026-07-21"]
    # 旧日期值未被改写，新日期入库
    assert nav_history_repo.list_range(conn, "110011", 10)[0]["nav"] == 1.4


async def test_intraday_does_not_force_refresh(conn, monkeypatch):
    """盘中（15:30 前）：DB 有旧数据也直接返回，不强制拉上游。"""

    class _IntradayDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 21, 10, 30, tzinfo=CST)

    monkeypatch.setattr(nav_history_svc, "datetime", _IntradayDatetime)
    nav_history_repo.upsert_many(conn, "110011", _rows(("2026-07-20", 1.4, 1.5)))

    async def _boom(code, limit=365):
        raise AssertionError("盘中不应请求上游")

    monkeypatch.setattr(nav_history_svc, "fetch_nav_history", _boom)

    out = await nav_history_svc.get_nav_history(conn, "110011", 365)
    assert out == [
        {"date": "2026-07-20", "nav": 1.4, "accNav": 1.5, "dailyReturn": None}
    ]
