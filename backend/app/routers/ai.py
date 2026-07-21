"""AI-powered fund selection endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..core import sse_response
from ..schemas import AiSelectPayload
from ..services.ai_agent import agent_loop

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/select/stream")
async def ai_select_stream(payload: AiSelectPayload) -> StreamingResponse:
    """Agentic AI fund selection with SSE streaming.

    Yields text/event-stream events:
      {"type":"step",   "text":"..."}      — progress update
      {"type":"result", "data":{...}}      — final recommendations
      {"type":"error",  "text":"..."}      — fatal error
    """
    return sse_response(
        agent_loop(
            payload.theme,
            payload.emphasis,
            provider=payload.provider,
            api_key=payload.api_key,
            base_url=payload.base_url,
            model=payload.model,
            analysis_model=payload.analysis_model,
        )
    )
