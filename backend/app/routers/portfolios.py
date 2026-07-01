"""Portfolio CRUD: list, create, rename, delete."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_conn

router = APIRouter(tags=["portfolios"])


class PortfolioPayload(BaseModel):
    name: str


@router.get("/api/portfolios")
def list_portfolios() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.id, p.name, p.created_at,
                      COUNT(pos.id) AS fund_count
               FROM portfolios p
               LEFT JOIN positions pos ON pos.portfolio_id = p.id
               GROUP BY p.id ORDER BY p.created_at DESC"""
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/api/portfolios")
def create_portfolio(payload: PortfolioPayload) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="组合名称不能为空")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO portfolios(name, created_at) VALUES(?, ?)", (name, now)
        )
        conn.commit()
    return {"ok": True, "id": cur.lastrowid, "name": name}


@router.patch("/api/portfolios/{portfolio_id}")
def rename_portfolio(portfolio_id: int, payload: PortfolioPayload) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="组合名称不能为空")
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM portfolios WHERE id=?", (portfolio_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="组合不存在")
        conn.execute("UPDATE portfolios SET name=? WHERE id=?", (name, portfolio_id))
        conn.commit()
    return {"ok": True, "id": portfolio_id, "name": name}


@router.delete("/api/portfolios/{portfolio_id}")
def delete_portfolio(portfolio_id: int) -> dict:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM portfolios WHERE id=?", (portfolio_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="组合不存在")
        conn.execute("DELETE FROM positions WHERE portfolio_id=?", (portfolio_id,))
        conn.execute(
            "DELETE FROM transactions WHERE portfolio_id=?", (portfolio_id,)
        )
        conn.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
        conn.commit()
    return {"ok": True, "id": portfolio_id}
