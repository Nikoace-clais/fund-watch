"""DCA (定投) plans, records, and stats."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..core import CST, validate_code
from ..db import get_conn
from ..schemas import (
    AddDcaRecordPayload,
    CreateDcaPlanPayload,
    PatchDcaPlanPayload,
    PatchDcaRecordPayload,
)
from ..services.dca import calc_dca_stats

router = APIRouter(tags=["dca"])


@router.post("/api/dca/plans")
def create_dca_plan(payload: CreateDcaPlanPayload) -> dict:
    validate_code(payload.code)
    now = datetime.now(CST).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO dca_plans(code,name,amount,frequency,day_of_week,day_of_month,
               start_date,end_date,is_active,created_at)
               VALUES(?,?,?,?,?,?,?,?,1,?)""",
            (payload.code, payload.name, payload.amount, payload.frequency,
             payload.day_of_week, payload.day_of_month,
             payload.start_date, payload.end_date, now),
        )
        conn.commit()
        plan_id = cur.lastrowid
    return {"ok": True, "id": plan_id}


@router.get("/api/dca/plans")
def list_dca_plans() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM dca_plans ORDER BY created_at DESC"
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/api/dca/stats")
def get_all_dca_stats() -> dict:
    with get_conn() as conn:
        plans = conn.execute("SELECT id FROM dca_plans").fetchall()
        items = [calc_dca_stats(p["id"], conn) for p in plans]
    return {"items": items}


@router.get("/api/dca/plans/{plan_id}")
def get_dca_plan(plan_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM dca_plans WHERE id=?", (plan_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="plan not found")
    return dict(row)


@router.patch("/api/dca/plans/{plan_id}")
def patch_dca_plan(plan_id: int, payload: PatchDcaPlanPayload) -> dict:
    PATCHABLE_DCA_PLAN_FIELDS = {"name", "amount", "frequency", "day_of_week", "day_of_month", "end_date", "is_active"}
    updates = {k: v for k, v in payload.model_dump().items() if v is not None and k in PATCHABLE_DCA_PLAN_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE dca_plans SET {set_clause} WHERE id=?",
            (*updates.values(), plan_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="plan not found")
    return {"ok": True}


@router.delete("/api/dca/plans/{plan_id}")
def delete_dca_plan(plan_id: int) -> dict:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM dca_plans WHERE id=?", (plan_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="plan not found")
    return {"ok": True}


@router.get("/api/dca/plans/{plan_id}/records")
def list_dca_records(plan_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT r.*, t.nav, t.shares, t.amount as tx_amount
               FROM dca_records r
               LEFT JOIN transactions t ON t.id = r.transaction_id
               WHERE r.plan_id=?
               ORDER BY r.scheduled_date DESC""",
            (plan_id,),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/api/dca/plans/{plan_id}/records")
def add_dca_record(plan_id: int, payload: AddDcaRecordPayload) -> dict:
    if payload.status not in ("success", "failed"):
        raise HTTPException(status_code=400, detail="status must be success or failed")
    if payload.status == "success" and payload.transaction_id is None:
        raise HTTPException(status_code=400, detail="success record requires transaction_id")
    now = datetime.now(CST).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO dca_records(plan_id,scheduled_date,status,transaction_id,note,created_at)
               VALUES(?,?,?,?,?,?)""",
            (plan_id, payload.scheduled_date, payload.status,
             payload.transaction_id, payload.note, now),
        )
        conn.commit()
    return {"ok": True, "id": cur.lastrowid}


@router.patch("/api/dca/records/{record_id}")
def patch_dca_record(record_id: int, payload: PatchDcaRecordPayload) -> dict:
    PATCHABLE_RECORD_FIELDS = {"status", "transaction_id", "note"}
    updates = {
        k: v
        for k, v in payload.model_dump().items()
        if k in payload.model_fields_set and k in PATCHABLE_RECORD_FIELDS
    }
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    if "status" in updates and updates["status"] not in ("success", "failed"):
        raise HTTPException(status_code=400, detail="status must be success or failed")
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE dca_records SET {set_clause} WHERE id=?",
            (*updates.values(), record_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True}


@router.delete("/api/dca/records/{record_id}")
def delete_dca_record(record_id: int) -> dict:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM dca_records WHERE id=?", (record_id,))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="record not found")
    return {"ok": True}


@router.get("/api/dca/plans/{plan_id}/stats")
def get_dca_plan_stats(plan_id: int) -> dict:
    with get_conn() as conn:
        return calc_dca_stats(plan_id, conn)
