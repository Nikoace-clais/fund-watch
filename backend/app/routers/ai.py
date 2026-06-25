"""AI-powered fund selection endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..fund_source import _SECTOR_KEYWORDS
from ..schemas import AiSelectPayload
from ..services.ai_select import select_funds

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/sectors")
async def list_sectors() -> dict:
    """Return the list of supported sector keywords."""
    return {"sectors": list(_SECTOR_KEYWORDS)}


@router.post("/select")
async def ai_select(payload: AiSelectPayload) -> dict:
    """AI-powered fund selection.

    Body: {"theme": "半导体", "emphasis": "稳健低回撤"}
    Returns ranked recommendations with AI reasoning.
    """
    try:
        result = await select_funds(payload.theme, payload.emphasis)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 选基失败: {e}")
    return result
