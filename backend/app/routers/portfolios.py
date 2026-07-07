"""Portfolio CRUD: list, create, rename, delete."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_request_conn
from ..repositories import portfolios_repo, positions_repo, tx_repo

router = APIRouter(tags=["portfolios"])


class PortfolioPayload(BaseModel):
    name: str


@router.get("/api/portfolios")
def list_portfolios(
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    return {"items": portfolios_repo.list_all(conn)}


@router.post("/api/portfolios")
def create_portfolio(
    payload: PortfolioPayload, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="组合名称不能为空")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    new_id = portfolios_repo.create(conn, name, now)
    return {"ok": True, "id": new_id, "name": name}


@router.patch("/api/portfolios/{portfolio_id}")
def rename_portfolio(
    portfolio_id: int,
    payload: PortfolioPayload,
    conn: sqlite3.Connection = Depends(get_request_conn),
) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="组合名称不能为空")
    if not portfolios_repo.exists(conn, portfolio_id):
        raise HTTPException(status_code=404, detail="组合不存在")
    portfolios_repo.rename(conn, portfolio_id, name)
    return {"ok": True, "id": portfolio_id, "name": name}


@router.delete("/api/portfolios/{portfolio_id}")
def delete_portfolio(
    portfolio_id: int, conn: sqlite3.Connection = Depends(get_request_conn)
) -> dict[str, Any]:
    if not portfolios_repo.exists(conn, portfolio_id):
        raise HTTPException(status_code=404, detail="组合不存在")
    positions_repo.delete_all_for_portfolio(conn, portfolio_id)
    tx_repo.delete_all_for_portfolio(conn, portfolio_id)
    portfolios_repo.delete(conn, portfolio_id)
    return {"ok": True, "id": portfolio_id}
