"""Screenshot recognition endpoints (PaddleOCR → text AI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ..ocr_service import extract_transaction_from_text, is_ready, ocr_text
from ..services.ocr_pipeline import (
    ai_error,
    build_cfg,
    ocr_fund_generator,
    unique_upload_path,
)

router = APIRouter(tags=["ocr"])


@router.get("/api/ocr/status")
def ocr_status() -> dict[str, Any]:
    return {"ready": is_ready()}


@router.post("/api/ocr/fund-code")
async def ocr_fund_code(
    files: list[UploadFile] = File(...),
    provider: str = Form("anthropic"),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
    model: str | None = Form(None),
    analysis_model: str | None = Form(None),
) -> StreamingResponse:
    cfg = build_cfg(provider, api_key, base_url, model, review_model=analysis_model)
    # Read file bytes eagerly (UploadFile is not safe to use after response starts)
    files_data = [(f.filename or "upload.png", await f.read()) for f in files]
    return StreamingResponse(
        ocr_fund_generator(files_data, cfg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/ocr/transaction")
async def ocr_transaction(
    file: UploadFile = File(...),
    provider: str = Form("anthropic"),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
    model: str | None = Form(None),
) -> dict[str, Any]:
    cfg = build_cfg(provider, api_key, base_url, model)
    image_bytes = await file.read()

    path = unique_upload_path(file.filename, "ocr_tx")
    path.write_bytes(image_bytes)

    raw_text = await run_in_threadpool(ocr_text, path)

    try:
        tx_data = await extract_transaction_from_text(raw_text, cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=ai_error(e)) from e

    return {
        "ok": True,
        "image": path.name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
