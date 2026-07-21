"""Health check."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..core import utc_now_iso

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "time": utc_now_iso()}
