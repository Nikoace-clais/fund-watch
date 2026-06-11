"""Health check."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}
