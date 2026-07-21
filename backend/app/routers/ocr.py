"""Screenshot recognition endpoints (PaddleOCR → text AI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..core import read_upload_limited, sse_response
from ..ocr_service import extract_transaction_from_text, is_ready
from ..services.ocr_pipeline import (
    MAX_UPLOAD_BYTES,
    OcrFailedError,
    ai_error,
    build_cfg,
    ocr_bytes_to_text,
    ocr_fund_generator,
    validate_upload,
)

router = APIRouter(tags=["ocr"])

_OCR_FAIL_DETAIL = "图片文字识别失败，请上传清晰的截图"
_IMG_SIZE_DETAIL = "图片过大，单张上限 10MB"


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
    files_data = []
    for f in files:
        data = await read_upload_limited(f, MAX_UPLOAD_BYTES, _IMG_SIZE_DETAIL)
        validate_upload(f.filename, len(data))
        files_data.append((f.filename or "upload.png", data))
    return sse_response(ocr_fund_generator(files_data, cfg))


@router.post("/api/ocr/transaction")
async def ocr_transaction(
    file: UploadFile = File(...),
    provider: str = Form("anthropic"),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
    model: str | None = Form(None),
) -> dict[str, Any]:
    cfg = build_cfg(provider, api_key, base_url, model)
    image_bytes = await read_upload_limited(file, MAX_UPLOAD_BYTES, _IMG_SIZE_DETAIL)
    validate_upload(file.filename, len(image_bytes))

    try:
        raw_text, image_name = await ocr_bytes_to_text(
            file.filename, image_bytes, prefix="ocr_tx"
        )
    except OcrFailedError as e:
        # 非图片内容/损坏文件会让 PaddleOCR 抛异常 → 400 中文提示而非裸 500
        raise HTTPException(status_code=400, detail=_OCR_FAIL_DETAIL) from e

    try:
        tx_data = await extract_transaction_from_text(raw_text, cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=ai_error(e)) from e

    return {
        "ok": True,
        "image": image_name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
