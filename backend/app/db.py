from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

from .core import utc_now_iso

# FUND_WATCH_DB overrides the default path (used by tests for isolation)
DB_PATH = Path(
    os.environ.get("FUND_WATCH_DB")
    or Path(__file__).resolve().parents[1] / "data" / "fund_watch.db"
)


def _current_db_path() -> Path:
    return Path(os.environ.get("FUND_WATCH_DB") or DB_PATH)


def _open_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Short-lived connection for scripts and the background scheduler.

    Callers are responsible for their own commit(); use get_request_conn
    inside FastAPI request handlers instead so one connection spans the
    whole request.
    """
    conn = _open_conn(_current_db_path())
    try:
        yield conn
    finally:
        conn.close()


def get_request_conn() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: one connection per request, committed atomically.

    FastAPI caches dependency results per request, so every
    Depends(get_request_conn) in the same request path shares this
    connection — repository calls that used to open their own connection
    now compose into a single transaction.
    """
    conn = _open_conn(_current_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def prune_old_snapshots(keep_days: int = 30) -> int:
    """分层清理：每日 id 最大一条永久保留，其余盘中快照超过 keep_days 删除。

    Returns number of rows deleted."""
    from .repositories import snapshot_repo

    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    with get_conn() as conn:
        deleted = snapshot_repo.prune_older_than(conn, cutoff)
        conn.commit()
    return deleted


# Bump when adding a migration step in _apply_migrations.
SCHEMA_VERSION = 3

# funds columns that only ever existed to support the one-time single-pool
# migration below; positions is the source of truth, these are pure legacy.
_LEGACY_FUNDS_COLUMNS = [
    "amount",
    "percentage",
    "holding_shares",
    "imported_holding_amount",
    "imported_cumulative_return",
    "imported_holding_return",
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Additive column migrations, gated by PRAGMA user_version.

    Each step runs at most once (tracked via user_version) instead of on
    every init_db() call; ALTER TABLE ADD COLUMN has no IF NOT EXISTS in
    SQLite, so the try/except stays as a defensive fallback for DBs that
    already have the column from before this versioning existed.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]

    if current < 1:
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
        current = 1

    if current < 2:
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN portfolio_id INTEGER")
        except sqlite3.OperationalError:
            pass  # column already exists
        current = 2

    conn.execute(f"PRAGMA user_version = {current}")


def _drop_legacy_funds_columns(conn: sqlite3.Connection) -> None:
    """Drop funds' one-time migration columns (version 3) once their data
    has been copied into positions by _migrate_single_pool_to_default_portfolio.

    Must run after that copy, not inside _apply_migrations (which runs
    before it in init_db) — dropping first would silently lose any
    not-yet-migrated legacy holding data.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= 3:
        return
    for col in _LEGACY_FUNDS_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE funds DROP COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # already dropped, or column never existed
    conn.execute("PRAGMA user_version = 3")


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
        _apply_migrations(conn)
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

        # 净值历史底座：每日收盘净值落库，供图表/指标计算 DB 优先读取
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fund_nav_history (
                code        TEXT NOT NULL,
                date        TEXT NOT NULL,          -- YYYY-MM-DD（CST 交易日）
                nav         REAL NOT NULL,
                acc_nav     REAL,                   -- 累计净值（源有则存）
                daily_return REAL,                  -- 日涨幅%（源 equityReturn）
                captured_at TEXT NOT NULL,
                PRIMARY KEY (code, date)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_nav_history_date ON fund_nav_history(date)"
        )

        _migrate_single_pool_to_default_portfolio(conn)
        _drop_legacy_funds_columns(conn)
        conn.commit()


def _migrate_single_pool_to_default_portfolio(conn: sqlite3.Connection) -> None:
    """One-time: move legacy single-pool holdings/transactions into a default portfolio.

    Idempotent: runs only when no portfolio exists yet AND there is legacy data
    (a fund with position fields, or any transaction). positions is the
    source of truth from now on; the funds columns read here are dropped
    right after by _drop_legacy_funds_columns.
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

    now = utc_now_iso()
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
