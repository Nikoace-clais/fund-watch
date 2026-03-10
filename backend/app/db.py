from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "fund_watch.db"


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


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
        # Migration: add sector, amount columns to funds
        for col, coltype in [
            ("sector", "TEXT"),
            ("amount", "REAL"),
            ("percentage", "REAL"),
            ("amount_mode", "TEXT DEFAULT 'manual'"),
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_code ON transactions(code)"
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
        conn.commit()
