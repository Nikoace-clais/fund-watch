"""Tests for the funds-table legacy-column migration (db.py).

The migration must copy any legacy single-pool holding data into
positions *before* dropping the now-unused funds columns — reordering
these two steps would silently discard un-migrated holdings.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app.db import init_db


def _seed_legacy_db(db_path: str) -> None:
    """A pre-multi-portfolio funds table with legacy holding data, user_version=0."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE funds (
            code TEXT PRIMARY KEY, name TEXT, created_at TEXT NOT NULL,
            sector TEXT, amount REAL, percentage REAL, holding_shares TEXT,
            imported_holding_amount REAL, imported_cumulative_return REAL,
            imported_holding_return REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL,
            direction TEXT NOT NULL, trade_date TEXT NOT NULL, nav TEXT NOT NULL,
            shares TEXT NOT NULL, amount TEXT NOT NULL, fee TEXT NOT NULL DEFAULT '0',
            note TEXT, source TEXT DEFAULT 'manual', created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO funds(code,name,created_at,holding_shares,imported_holding_amount)"
        " VALUES (?,?,?,?,?)",
        ("110011", "易方达优质精选", "2025-01-01T00:00:00", "1000.00", 5000.0),
    )
    conn.commit()
    conn.close()


def test_legacy_holdings_survive_column_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.db as app_db

    db_path = tmp_path / "legacy.db"
    _seed_legacy_db(str(db_path))
    monkeypatch.setattr(app_db, "DB_PATH", db_path)

    init_db()

    with app_db.get_conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(funds)").fetchall()}
        assert cols == {"code", "name", "created_at", "sector"}

        pos = conn.execute(
            "SELECT holding_shares, imported_holding_amount "
            "FROM positions WHERE code=?",
            ("110011",),
        ).fetchone()
        assert pos["holding_shares"] == "1000.00"
        assert pos["imported_holding_amount"] == 5000.0

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == app_db.SCHEMA_VERSION


def test_fresh_install_ends_with_no_legacy_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.db as app_db

    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "fresh.db")
    init_db()

    with app_db.get_conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(funds)").fetchall()}
        assert cols == {"code", "name", "created_at", "sector"}
