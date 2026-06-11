"""Screenshot OCR endpoints (rapidocr)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from ..core import UPLOAD_DIR
from ..db import get_conn
from ..fund_source import search_fund_by_name
from ..ocr_service import (
    extract_fund_codes_from_image,
    extract_fund_names_from_text,
    extract_funds_with_amounts,
    extract_transaction_from_image,
)

router = APIRouter(tags=["ocr"])


@router.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, codes = extract_fund_codes_from_image(path)
    _, matched_funds = extract_funds_with_amounts(path)

    # If no codes found, try to extract fund names and search for codes
    name_matches: list[dict] = []
    if not codes:
        fund_names = extract_fund_names_from_text(raw_text)
        seen_codes: set[str] = set()
        for name in fund_names[:5]:  # limit to avoid too many API calls
            try:
                results = await search_fund_by_name(name, limit=1)
                for r in results:
                    if r["code"] not in seen_codes:
                        seen_codes.add(r["code"])
                        name_matches.append({
                            "code": r["code"],
                            "name": r.get("name", ""),
                            "matched_keyword": name,
                            "type": r.get("type"),
                        })
            except Exception:
                continue
        # Add name-matched codes to the codes list
        codes = list(seen_codes)

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at) VALUES(?,?,?,?)",
            (path.name, raw_text, json.dumps(codes, ensure_ascii=False), now),
        )
        conn.commit()

    return {
        "ok": True,
        "image": path.name,
        "matched_codes": codes,
        "matched_funds": matched_funds if matched_funds else name_matches,
        "name_matches": name_matches,
        "raw_text": raw_text,
        "saved_at": now,
    }


@router.post("/api/ocr/transaction")
async def ocr_transaction(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_tx_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, tx_data = extract_transaction_from_image(path)

    return {
        "ok": True,
        "image": path.name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
