"""Fund repository for database operations."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "fund_watch.db"


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Get database connection with proper settings."""
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


def init_db() -> None:
    """Initialize database schema."""
    with get_conn() as conn:
        # Create tables
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS funds (
                code TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        
        # Add migration columns
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('buy','sell')),
                trade_date TEXT NOT NULL,
                nav TEXT NOT NULL,
                shares TEXT NOT NULL,
                amount TEXT NOT NULL,
                fee TEXT NOT NULL DEFAULT '0',
                note TEXT,
                source TEXT DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_code ON transactions(code)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dca_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT,
                amount TEXT NOT NULL CHECK(CAST(amount AS REAL) > 0),
                frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','biweekly','monthly')),
                day_of_week INTEGER CHECK(day_of_week IS NULL OR day_of_week BETWEEN 0 AND 6),
                day_of_month INTEGER CHECK(day_of_month IS NULL OR day_of_month BETWEEN 1 AND 28),
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dca_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL REFERENCES dca_plans(id) ON DELETE CASCADE,
                scheduled_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('success','failed')),
                transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dca_records_plan ON dca_records(plan_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dca_plans_code ON dca_plans(code)"
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
            "CREATE INDEX IF NOT EXISTS idx_snapshots_code_id ON fund_snapshots(code, id DESC)"
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


def prune_old_snapshots(keep_days: int = 30) -> int:
    """Delete snapshots older than keep_days."""
    cutoff = (
        datetime.now(timezone.utc) - __import__("datetime").timedelta(days=keep_days)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM fund_snapshots WHERE captured_at < ?", (cutoff,)
        )
        conn.commit()
    return cur.rowcount


class FundRepository:
    """Repository for fund operations."""
    
    def get_all(self) -> list[dict]:
        """Get all funds."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM funds ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_by_code(self, code: str) -> dict | None:
        """Get fund by code."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM funds WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None
    
    def create(self, code: str, name: str | None = None) -> dict:
        """Create new fund."""
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO funds (code, name, created_at) VALUES (?, ?, ?)",
                (code, name, now)
            )
            conn.commit()
            return self.get_by_code(code)
    
    def delete(self, code: str) -> bool:
        """Delete fund and related data."""
        with get_conn() as conn:
            # Delete related records
            conn.execute("DELETE FROM transactions WHERE code = ?", (code,))
            conn.execute("DELETE FROM fund_snapshots WHERE code = ?", (code,))
            # Delete fund
            cur = conn.execute("DELETE FROM funds WHERE code = ?", (code,))
            conn.commit()
            return cur.rowcount > 0
    
    def batch_create(self, codes: list[str]) -> dict:
        """Batch create funds."""
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        with get_conn() as conn:
            for code in codes:
                try:
                    conn.execute(
                        "INSERT INTO funds (code, created_at) VALUES (?, ?)",
                        (code, now)
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass  # Already exists
            conn.commit()
        return {"inserted": inserted, "total": len(codes)}


def get_fund_repository() -> FundRepository:
    """Get fund repository instance."""
    return FundRepository()
