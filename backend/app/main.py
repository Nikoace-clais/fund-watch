from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .db import get_conn, init_db
from .fund_source import fetch_realtime_estimate
from .ocr_service import extract_fund_codes_from_image

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

app = FastAPI(title="Fund Watch API", version="0.2.0")


class BatchFundsPayload(BaseModel):
    codes: list[str]


@app.on_event("startup")
def startup() -> None:
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/funds")
def list_funds() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT code,name,created_at FROM funds ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows]}


def _validate_code(code: str) -> str:
    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code


@app.post("/api/funds/{code}")
def add_fund(code: str) -> dict:
    code = _validate_code(code)
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO funds(code,name,created_at) VALUES(?,?,?)",
            (code, None, now),
        )
        conn.commit()
    return {"ok": True, "code": code}


@app.post("/api/funds/batch")
def add_funds_batch(payload: BatchFundsPayload) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    valid: list[str] = []
    invalid: list[str] = []

    for c in payload.codes:
        c = c.strip()
        if c.isdigit() and len(c) == 6:
            valid.append(c)
        else:
            invalid.append(c)

    valid = sorted(set(valid))

    with get_conn() as conn:
        for code in valid:
            conn.execute(
                "INSERT OR IGNORE INTO funds(code,name,created_at) VALUES(?,?,?)",
                (code, None, now),
            )
        conn.commit()

    return {"ok": True, "added": valid, "invalid": invalid}


@app.get("/api/quote/{code}")
async def quote(code: str) -> dict:
    code = _validate_code(code)
    try:
        data = await fetch_realtime_estimate(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return data


@app.get("/api/funds/overview")
async def funds_overview() -> dict:
    with get_conn() as conn:
        funds = [dict(r) for r in conn.execute("SELECT code,name,created_at FROM funds ORDER BY created_at DESC").fetchall()]

    items: list[dict] = []
    for f in funds:
        code = f["code"]
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT code,name,gsz,gszzl,gztime,captured_at
                FROM fund_snapshots
                WHERE code=?
                ORDER BY id DESC LIMIT 1
                """,
                (code,),
            ).fetchone()

        latest_snapshot = dict(row) if row else None

        if latest_snapshot is None:
            try:
                q = await fetch_realtime_estimate(code)
                latest_snapshot = {
                    "code": code,
                    "name": q.get("name"),
                    "gsz": q.get("gsz"),
                    "gszzl": q.get("gszzl"),
                    "gztime": q.get("gztime"),
                    "captured_at": None,
                }
            except Exception:
                latest_snapshot = None

        items.append({"fund": f, "latest": latest_snapshot})

    return {"items": items}


@app.post("/api/snapshots/pull")
async def pull_snapshots() -> dict:
    with get_conn() as conn:
        codes = [r["code"] for r in conn.execute("SELECT code FROM funds").fetchall()]

    captured_at = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with get_conn() as conn:
        for code in codes:
            try:
                d = await fetch_realtime_estimate(code)
                conn.execute(
                    """
                    INSERT INTO fund_snapshots(code,name,dwjz,gsz,gszzl,gztime,captured_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        code,
                        d.get("name"),
                        d.get("dwjz"),
                        d.get("gsz"),
                        d.get("gszzl"),
                        d.get("gztime"),
                        captured_at,
                    ),
                )
                inserted += 1
            except Exception:
                continue
        conn.commit()

    return {"ok": True, "codes": len(codes), "inserted": inserted, "captured_at": captured_at}


@app.get("/api/snapshots/{code}")
def get_snapshots(code: str, limit: int = 50) -> dict:
    code = _validate_code(code)
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT code,name,dwjz,gsz,gszzl,gztime,captured_at
            FROM fund_snapshots
            WHERE code=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (code, limit),
        ).fetchall()
    items = [dict(r) for r in rows]
    items.reverse()
    return {"code": code, "count": len(items), "items": items}


@app.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, codes = extract_fund_codes_from_image(path)
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
        "raw_text": raw_text,
        "saved_at": now,
    }
