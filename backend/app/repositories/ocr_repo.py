"""SQL for the ocr_records table."""

from __future__ import annotations

import sqlite3


def insert(
    conn: sqlite3.Connection,
    *,
    image_name: str | None,
    raw_text: str | None,
    matched_codes: str | None,
    created_at: str,
) -> None:
    conn.execute(
        "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at)"
        " VALUES(?,?,?,?)",
        (image_name, raw_text, matched_codes, created_at),
    )
