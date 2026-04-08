"""Pydantic schemas for API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FundBase(BaseModel):
    """Base fund model."""
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str | None = None


class FundCreate(FundBase):
    """Fund creation request."""
    pass


class Fund(FundBase):
    """Fund response."""
    created_at: datetime
    sector: str | None = None
    amount: float | None = None
    percentage: float | None = None

    class Config:
        from_attributes = True


class FundOverview(BaseModel):
    """Fund with latest quote."""
    code: str
    name: str | None
    sector: str | None
    created_at: datetime
    latest_quote: Quote | None = None


class Quote(BaseModel):
    """Real-time fund quote."""
    fundcode: str
    name: str | None = None
    jzrq: str | None = None  # 净值日期
    dwjz: float | None = None  # 单位净值
    gsz: float | None = None  # 估算净值
    gszzl: float | None = None  # 估算涨跌幅
    gztime: str | None = None  # 估算时间


class Snapshot(BaseModel):
    """Fund snapshot captured at specific time."""
    id: int
    code: str
    name: str | None = None
    dwjz: float | None = None
    gsz: float | None = None
    gszzl: float | None = None
    gztime: str | None = None
    captured_at: datetime

    class Config:
        from_attributes = True


class Transaction(BaseModel):
    """Fund transaction record."""
    id: int
    code: str
    direction: Literal["buy", "sell"]
    trade_date: str
    nav: Decimal
    shares: Decimal
    amount: Decimal
    fee: Decimal = Decimal("0")
    note: str | None = None
    source: str = "manual"
    created_at: datetime

    class Config:
        from_attributes = True


class FundBatchImport(BaseModel):
    """Batch import request from AI/OCR."""
    codes: list[str]
    
    @field_validator("codes")
    @classmethod
    def validate_codes(cls, v: list[str]) -> list[str]:
        """Validate all codes are 6-digit numeric strings."""
        for code in v:
            if not code.isdigit() or len(code) != 6:
                raise ValueError(f"Invalid fund code: {code}")
        return v


class ImportPreview(BaseModel):
    """Import preview with confidence scores."""
    code: str
    name: str | None = None
    confidence: float  # 0.0 - 1.0
    source: Literal["code", "name_match", "table_structure"]
    needs_review: bool = False


class ImportResult(BaseModel):
    """Import result with details."""
    funds: list[ImportPreview]
    total_confidence: float
    needs_review: bool
