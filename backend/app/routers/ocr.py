"""Screenshot OCR endpoints (rapidocr)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..core import UPLOAD_DIR
from ..db import get_conn
from ..fund_source import search_fund_by_name
from ..ocr_service import (
    extract_fund_names_from_text,
    extract_transaction_from_image,
    scan_fund_image,
)

router = APIRouter(tags=["ocr"])


def _unique_upload_path(filename: str | None, prefix: str) -> Path:
    suffix = Path(filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return UPLOAD_DIR / f"{prefix}_{ts}_{uuid4().hex[:8]}{suffix}"


@router.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    path = _unique_upload_path(file.filename, "ocr")
    path.write_bytes(await file.read())

    # OCR inference is CPU-heavy and synchronous — keep it off the event loop
    raw_text, codes, matched_funds = await run_in_threadpool(scan_fund_image, path)

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
    path = _unique_upload_path(file.filename, "ocr_tx")
    path.write_bytes(await file.read())

    raw_text, tx_data = await run_in_threadpool(extract_transaction_from_image, path)

    return {
        "ok": True,
        "image": path.name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
