"""snapshot_repo.prune_older_than 分层保留测试。

语义：每个自然日 id 最大（最接近收盘）的一条快照永久保留；
其余盘中快照超过保留期（cutoff）才删除。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import app.db as app_db
import pytest
from app.repositories import snapshot_repo

_BASE = datetime(2026, 5, 20, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "test.db")
    app_db.init_db()
    with app_db.get_conn() as c:
        yield c


def _seed_40_days(conn) -> None:
    """40 个自然日 × 每日 3 条快照（id 递增 ⇒ 每日最后插入的一条 id 最大）。"""
    for day in range(40):
        d = _BASE + timedelta(days=day)
        for hour in (2, 6, 7):  # UTC 时刻，均落在同一 UTC 自然日内
            snapshot_repo.insert(
                conn,
                code="110011",
                name="测试基金",
                dwjz=1.0,
                gsz=1.0,
                gszzl=0.1,
                gztime=None,
                captured_at=d.replace(hour=hour).isoformat(),
            )


def test_prune_keeps_daily_close_and_deletes_old_intraday(conn):
    _seed_40_days(conn)

    cutoff = (_BASE + timedelta(days=10)).isoformat()  # 模拟保留最近 30 天
    deleted = snapshot_repo.prune_older_than(conn, cutoff)
    assert deleted == 20  # 超过保留期的 10 天 × 每天删 2 条盘中快照

    # 每个自然日至少留下当日收盘快照；30 天内的日子不受影响
    rows = conn.execute(
        "SELECT date(captured_at) AS d, COUNT(*) AS n"
        " FROM fund_snapshots GROUP BY d ORDER BY d"
    ).fetchall()
    assert len(rows) == 40
    for i, r in enumerate(rows):
        assert r["n"] == (1 if i < 10 else 3)

    # 超过保留期的日子，留下的正是当日 id 最大（07:00 那条，最接近收盘）
    kept = conn.execute(
        "SELECT captured_at FROM fund_snapshots WHERE captured_at < ? ORDER BY id",
        (cutoff,),
    ).fetchall()
    assert [r["captured_at"][11:13] for r in kept] == ["07"] * 10
