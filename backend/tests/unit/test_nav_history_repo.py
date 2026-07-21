"""nav_history_repo 测试：upsert 幂等覆盖、list_range 排序/limit、latest_date。"""

from __future__ import annotations

import app.db as app_db
import pytest
from app.repositories import nav_history_repo


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """独立临时库；同一连接内写入对后续读取立即可见。"""
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    with app_db.get_conn() as c:
        yield c


def _rows(*items):
    """构造 fetch_nav_history 返回形状的行：(date, nav, accNav)。"""
    return [
        {"date": d, "nav": n, "accNav": a, "dailyReturn": None} for d, n, a in items
    ]


class TestUpsertMany:
    def test_idempotent_overwrite_same_date(self, conn):
        rows = _rows(("2026-07-20", 1.0, 1.1), ("2026-07-21", 1.02, 1.12))
        assert nav_history_repo.upsert_many(conn, "110011", rows) == 2

        # 同 (code, date) 重复 upsert → 覆盖而非报错/重复行
        assert (
            nav_history_repo.upsert_many(
                conn, "110011", _rows(("2026-07-21", 1.05, 1.15))
            )
            == 1
        )

        out = nav_history_repo.list_range(conn, "110011", 10)
        assert len(out) == 2
        assert out[-1] == {
            "date": "2026-07-21",
            "nav": 1.05,
            "accNav": 1.15,
            "dailyReturn": None,
        }

    def test_daily_return_roundtrip(self, conn):
        # 源字段 equityReturn → daily_return 列 → 响应 dailyReturn，前端风险指标依赖
        rows = [
            {"date": "2026-07-21", "nav": 1.02, "accNav": 1.12, "dailyReturn": 1.96}
        ]
        nav_history_repo.upsert_many(conn, "110011", rows)
        out = nav_history_repo.list_range(conn, "110011", 10)
        assert out[0]["dailyReturn"] == 1.96

    def test_skips_rows_missing_date_or_nav(self, conn):
        rows = [
            {"date": None, "nav": 1.0, "accNav": None},
            {"date": "2026-07-21", "nav": None, "accNav": None},
            {"date": "2026-07-21", "nav": 1.0, "accNav": None},
        ]
        assert nav_history_repo.upsert_many(conn, "110011", rows) == 1
        assert nav_history_repo.latest_date(conn, "110011") == "2026-07-21"


class TestListRange:
    def test_ascending_order_and_limit(self, conn):
        rows = _rows(
            ("2026-07-17", 1.0, None),
            ("2026-07-21", 1.4, None),
            ("2026-07-18", 1.1, None),
            ("2026-07-20", 1.3, None),
            ("2026-07-19", 1.2, None),
        )
        nav_history_repo.upsert_many(conn, "110011", rows)

        out = nav_history_repo.list_range(conn, "110011", 3)
        assert [r["date"] for r in out] == ["2026-07-19", "2026-07-20", "2026-07-21"]
        assert [r["nav"] for r in out] == [1.2, 1.3, 1.4]

    def test_limit_larger_than_data_returns_all(self, conn):
        nav_history_repo.upsert_many(conn, "110011", _rows(("2026-07-20", 1.0, None)))
        assert len(nav_history_repo.list_range(conn, "110011", 365)) == 1


class TestLatestDate:
    def test_empty_returns_none(self, conn):
        assert nav_history_repo.latest_date(conn, "110011") is None

    def test_returns_max_date(self, conn):
        nav_history_repo.upsert_many(
            conn, "110011", _rows(("2026-07-20", 1.0, None), ("2026-07-21", 1.1, None))
        )
        assert nav_history_repo.latest_date(conn, "110011") == "2026-07-21"
