from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import get_conn, init_db
from .fund_source import fetch_fund_info, fetch_realtime_estimate
from .ocr_service import extract_fund_codes_from_image, extract_funds_with_amounts

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

app = FastAPI(title="Fund Watch API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AddFundPayload(BaseModel):
    amount: float | None = None


class BatchFundsPayload(BaseModel):
    codes: list[str]
    amounts: dict[str, float] | None = None


class UpdateFundPayload(BaseModel):
    amount: float | None = None
    sector: str | None = None


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
        rows = conn.execute("SELECT code,name,sector,amount,percentage,created_at FROM funds ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows]}


def _validate_code(code: str) -> str:
    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code


@app.post("/api/funds/recalc-percentage")
def recalc_percentage() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT code, amount FROM funds").fetchall()
        total = sum(r["amount"] for r in rows if r["amount"])
        if total > 0:
            for r in rows:
                pct = round((r["amount"] / total) * 100, 2) if r["amount"] else None
                conn.execute("UPDATE funds SET percentage=? WHERE code=?", (pct, r["code"]))
        conn.commit()
    return {"ok": True, "total": total}


@app.post("/api/funds/{code}")
async def add_fund(code: str, payload: AddFundPayload | None = None) -> dict:
    code = _validate_code(code)
    now = datetime.now(timezone.utc).isoformat()

    # Fetch fund info (name + sector) from data source
    name = None
    sector = None
    try:
        info = await fetch_fund_info(code)
        name = info.get("name")
        sector = info.get("sector")
    except Exception:
        pass

    amount = payload.amount if payload else None

    with get_conn() as conn:
        existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
        if existing:
            if amount is not None:
                conn.execute("UPDATE funds SET amount=? WHERE code=?", (amount, code))
            if sector and not conn.execute("SELECT sector FROM funds WHERE code=? AND sector IS NOT NULL", (code,)).fetchone():
                conn.execute("UPDATE funds SET sector=?, name=? WHERE code=?", (sector, name, code))
        else:
            conn.execute(
                "INSERT INTO funds(code,name,sector,amount,created_at) VALUES(?,?,?,?,?)",
                (code, name, sector, amount, now),
            )
        conn.commit()
    return {"ok": True, "code": code, "name": name, "sector": sector}


@app.post("/api/funds/batch")
async def add_funds_batch(payload: BatchFundsPayload) -> dict:
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
    amounts = payload.amounts or {}

    with get_conn() as conn:
        for code in valid:
            name = None
            sector = None
            try:
                info = await fetch_fund_info(code)
                name = info.get("name")
                sector = info.get("sector")
            except Exception:
                pass

            existing = conn.execute("SELECT code FROM funds WHERE code=?", (code,)).fetchone()
            if existing:
                updates = []
                params: list = []
                if name:
                    updates.append("name=?")
                    params.append(name)
                if sector:
                    updates.append("sector=?")
                    params.append(sector)
                amt = amounts.get(code)
                if amt is not None:
                    updates.append("amount=?")
                    params.append(amt)
                if updates:
                    params.append(code)
                    conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
            else:
                conn.execute(
                    "INSERT INTO funds(code,name,sector,amount,created_at) VALUES(?,?,?,?,?)",
                    (code, name, sector, amounts.get(code), now),
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
        funds = [dict(r) for r in conn.execute("SELECT code,name,sector,amount,percentage,created_at FROM funds ORDER BY created_at DESC").fetchall()]

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


@app.patch("/api/funds/{code}")
def update_fund(code: str, payload: UpdateFundPayload) -> dict:
    code = _validate_code(code)
    updates = []
    params: list = []
    if payload.amount is not None:
        updates.append("amount=?")
        params.append(payload.amount)
    if payload.sector is not None:
        updates.append("sector=?")
        params.append(payload.sector)
    if not updates:
        raise HTTPException(status_code=400, detail="nothing to update")
    params.append(code)
    with get_conn() as conn:
        conn.execute(f"UPDATE funds SET {','.join(updates)} WHERE code=?", params)
        conn.commit()
    return {"ok": True, "code": code}


@app.post("/api/ocr/fund-code")
async def ocr_fund_code(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = UPLOAD_DIR / f"ocr_{ts}{suffix}"
    path.write_bytes(await file.read())

    raw_text, codes = extract_fund_codes_from_image(path)
    _, matched_funds = extract_funds_with_amounts(path)

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
        "matched_funds": matched_funds,
        "raw_text": raw_text,
        "saved_at": now,
    }
