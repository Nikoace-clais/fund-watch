from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "fund_watch.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        for col, coltype in [("sector", "TEXT"), ("amount", "REAL"), ("percentage", "REAL")]:
            try:
                conn.execute(f"ALTER TABLE funds ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass  # column already exists

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
