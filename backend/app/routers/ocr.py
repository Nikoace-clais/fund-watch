"""Screenshot OCR endpoints (rapidocr)."""

from __future__ import annotations

import asyncio
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


_VERIFY_LIMIT = 15  # cap parallel verification calls per upload
_NAME_SEARCH_LIMIT = 5  # cap name-fallback search calls per upload


def _unique_upload_path(filename: str | None, prefix: str) -> Path:
    suffix = Path(filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return UPLOAD_DIR / f"{prefix}_{ts}_{uuid4().hex[:8]}{suffix}"


async def _resolve_code(code: str) -> dict | None:
    """Verify an OCR'd 6-digit candidate against the fund search source.

    Amounts and date fragments also match \\d{6}, so a candidate the source
    doesn't know is dropped (returns None). If the source itself fails we keep
    the candidate — recall over precision when we can't tell.
    """
    try:
        results = await search_fund_by_name(code, limit=1)
    except Exception:
        return {"code": code, "name": "", "type": None}
    for r in results:
        if r.get("code") == code:
            return {"code": code, "name": r.get("name", ""), "type": r.get("type")}
    return None


@router.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    path = _unique_upload_path(file.filename, "ocr")
    path.write_bytes(await file.read())

    # OCR inference is CPU-heavy and synchronous — keep it off the event loop
    raw_text, candidates, ocr_funds = await run_in_threadpool(scan_fund_image, path)

    # Drop 6-digit false positives (amounts, dates) via the fund search source
    resolved = await asyncio.gather(
        *[_resolve_code(c) for c in candidates[:_VERIFY_LIMIT]]
    )
    verified = [r for r in resolved if r is not None]
    codes = [r["code"] for r in verified]
    amount_by_code = {f["code"]: f.get("amount") for f in ocr_funds}
    matched_funds = [
        {"code": r["code"], "name": r["name"], "amount": amount_by_code.get(r["code"])}
        for r in verified
    ]

    # Always run the fund-name fallback and merge: many app screenshots show no
    # codes at all, and partially recognized shots miss some codes.
    name_matches: list[dict] = []
    seen_codes: set[str] = set(codes)
    fund_names = extract_fund_names_from_text(raw_text)
    for name in fund_names[:_NAME_SEARCH_LIMIT]:
        try:
            results = await search_fund_by_name(name, limit=1)
        except Exception:
            continue
        for r in results:
            if r["code"] in seen_codes:
                continue
            seen_codes.add(r["code"])
            name_matches.append(
                {
                    "code": r["code"],
                    "name": r.get("name", ""),
                    "matched_keyword": name,
                    "type": r.get("type"),
                }
            )
    codes = codes + [m["code"] for m in name_matches]

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at)"
            " VALUES(?,?,?,?)",
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
