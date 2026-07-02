"""Shared constants and helpers used across routers and services."""

from __future__ import annotations

import re
from datetime import timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

CST = timezone(timedelta(hours=8))

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

# ASCII-only digits: str.isdigit() also accepts non-decimal Unicode "digit"
# characters (e.g. superscripts) that aren't valid fund/stock codes.
_CODE_RE = re.compile(r"^[0-9]{6}$")


def is_valid_code(code: str) -> bool:
    """True if code is a bare 6-digit fund/stock code (no whitespace stripping)."""
    return bool(code) and bool(_CODE_RE.match(code))


def validate_code(code: str) -> str:
    code = code.strip()
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code
