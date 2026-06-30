from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

# FUND_WATCH_DB overrides the default path (used by tests for isolation)
DB_PATH = Path(
    os.environ.get("FUND_WATCH_DB")
    or Path(__file__).resolve().parents[1] / "data" / "fund_watch.db"
)


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def prune_old_snapshots(keep_days: int = 30) -> int:
    """Delete fund_snapshots older than keep_days. Returns number of rows deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM fund_snapshots WHERE captured_at < ?", (cutoff,)
        )
        conn.commit()
    return cur.rowcount


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS funds (
                code TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migration: add columns to funds
        for col, coltype in [
            ("sector", "TEXT"),
            ("amount", "REAL"),
            ("percentage", "REAL"),
            ("holding_shares", "TEXT"),
            ("imported_holding_amount", "REAL"),
            ("imported_cumulative_return", "REAL"),
            ("imported_holding_return", "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE funds ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass  # column already exists

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id                INTEGER NOT NULL,
                code                        TEXT NOT NULL,
                amount                      REAL,
                holding_shares              TEXT,
                imported_holding_amount     REAL,
                imported_cumulative_return  REAL,
                imported_holding_return     REAL,
                created_at                  TEXT NOT NULL,
                UNIQUE(portfolio_id, code)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_pf ON positions(portfolio_id)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT NOT NULL,
                direction   TEXT NOT NULL CHECK(direction IN ('buy','sell')),
                trade_date  TEXT NOT NULL,
                nav         TEXT NOT NULL,
                shares      TEXT NOT NULL,
                amount      TEXT NOT NULL,
                fee         TEXT NOT NULL DEFAULT '0',
                note        TEXT,
                source      TEXT DEFAULT 'manual',
                created_at  TEXT NOT NULL
            )
            """
        )
        # Migration: scope transactions to a portfolio
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN portfolio_id INTEGER")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_code ON transactions(code)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_pf_code"
            " ON transactions(portfolio_id, code)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fund_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT,
                dwjz REAL,
                gsz REAL,
                gszzl REAL,
                gztime TEXT,
                captured_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_code ON fund_snapshots(code)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_code_id"
            " ON fund_snapshots(code, id DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_name TEXT,
                raw_text TEXT,
                matched_codes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_industry (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT,
                industry   TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )

        _migrate_single_pool_to_default_portfolio(conn)
        conn.commit()


def _migrate_single_pool_to_default_portfolio(conn: sqlite3.Connection) -> None:
    """One-time: move legacy single-pool holdings/transactions into a default portfolio.

    Idempotent: runs only when no portfolio exists yet AND there is legacy data
    (a fund with position fields, or any transaction). funds keeps its old
    position columns unused — positions is the source of truth from now on.
    """
    if conn.execute("SELECT 1 FROM portfolios LIMIT 1").fetchone():
        return  # already migrated / multi-portfolio in use

    legacy_funds = conn.execute(
        """SELECT code, amount, holding_shares, imported_holding_amount,
                  imported_cumulative_return, imported_holding_return
           FROM funds
           WHERE holding_shares IS NOT NULL OR amount IS NOT NULL
              OR imported_holding_amount IS NOT NULL
              OR imported_cumulative_return IS NOT NULL
              OR imported_holding_return IS NOT NULL"""
    ).fetchall()
    has_tx = conn.execute("SELECT 1 FROM transactions LIMIT 1").fetchone()
    if not legacy_funds and not has_tx:
        return  # fresh install: let the import flow create the first portfolio

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cur = conn.execute(
        "INSERT INTO portfolios(name, created_at) VALUES(?, ?)", ("默认组合", now)
    )
    default_id = cur.lastrowid
    for f in legacy_funds:
        conn.execute(
            """INSERT INTO positions
               (portfolio_id, code, amount, holding_shares, imported_holding_amount,
                imported_cumulative_return, imported_holding_return, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                default_id,
                f["code"],
                f["amount"],
                f["holding_shares"],
                f["imported_holding_amount"],
                f["imported_cumulative_return"],
                f["imported_holding_return"],
                now,
            ),
        )
    conn.execute(
        "UPDATE transactions SET portfolio_id=? WHERE portfolio_id IS NULL",
        (default_id,),
    )
