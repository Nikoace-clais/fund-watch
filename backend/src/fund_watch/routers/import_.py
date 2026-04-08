"""Fund import router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..services.import_service import FundImportService

router = APIRouter(prefix="/api/import", tags=["import"])

# Service instance
import_service = FundImportService()


class ImportPreviewResponse(BaseModel):
    """Import preview response."""
    funds: list[dict[str, Any]]
    total_confidence: float
    needs_review: bool
    total_count: int


class ImportConfirmRequest(BaseModel):
    """Import confirm request."""
    codes: list[str]


class ImportConfirmResponse(BaseModel):
    """Import confirm response."""
    success: bool
    added: int
    total: int
    invalid: list[str]


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(file: UploadFile = File(...)) -> ImportPreviewResponse:
    """Preview fund import from image.
    
    Upload a screenshot/image containing fund information.
    Returns extracted funds with confidence scores.
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Read image data
    image_data = await file.read()
    
    if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB."
        )
    
    # Process image
    result = import_service.preview_import(image_data)
    
    # Convert to response format
    return ImportPreviewResponse(
        funds=[
            {
                "code": f.code,
                "name": f.name,
                "type": f.type,
                "confidence": round(f.confidence, 2),
                "source": f.source,
                "needs_review": f.needs_review,
            }
            for f in result.funds
        ],
        total_confidence=result.total_confidence,
        needs_review=result.needs_review,
        total_count=result.total_count,
    )


@router.post("/confirm", response_model=ImportConfirmResponse)
async def confirm_import(request: ImportConfirmRequest) -> ImportConfirmResponse:
    """Confirm import of selected funds.
    
    Pass the list of fund codes selected by user from the preview.
    """
    # Validate codes
    for code in request.codes:
        if not code.isdigit() or len(code) != 6:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fund code: {code}. Must be 6 digits."
            )
    
    # Import funds
    result = import_service.confirm_import(request.codes)
    
    return ImportConfirmResponse(
        success=result["success"],
        added=result["added"],
        total=result["total"],
        invalid=result["invalid"],
    )


@router.post("/ai", response_model=ImportPreviewResponse)
async def ai_import(file: UploadFile = File(...)) -> ImportPreviewResponse:
    """AI-assisted fund import (placeholder for future AI integration).
    
    Currently falls back to standard OCR + fuzzy matching.
    Future: Will use AI vision models for better recognition.
    """
    # For now, just call preview_import
    # This endpoint serves as a hook for future AI integration
    return await preview_import(file)
