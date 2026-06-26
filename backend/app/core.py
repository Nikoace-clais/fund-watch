"""Shared constants and helpers used across routers and services."""

from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

CST = timezone(timedelta(hours=8))

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"


def validate_code(code: str) -> str:
    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code
