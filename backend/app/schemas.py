"""Request payload models."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, field_validator


class AddFundPayload(BaseModel):
    amount: Decimal | None = None


class BatchFundItem(BaseModel):
    code: str | None = None
    name: str | None = None
    holding_amount: Decimal | None = None
    cumulative_return: Decimal | None = None
    holding_return: Decimal | None = None


class BatchFundsPayload(BaseModel):
    codes: list[str] = []
    amounts: dict[str, Decimal] | None = None
    funds: list[BatchFundItem] = []


class UpdateFundPayload(BaseModel):
    holding_shares: str | None = None
    sector: str | None = None


class AddTransactionPayload(BaseModel):
    direction: str  # 'buy' or 'sell'
    trade_date: str
    nav: str
    shares: str
    fee: str = "0"
    note: str | None = None
    source: str = "manual"


class CreateDcaPlanPayload(BaseModel):
    code: str
    name: str | None = None
    amount: str
    frequency: Literal["daily", "weekly", "biweekly", "monthly"]
    day_of_week: int | None = None
    day_of_month: int | None = None
    start_date: str
    end_date: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except InvalidOperation:
            raise ValueError("amount must be a valid decimal number")
        if d <= 0:
            raise ValueError("amount must be positive")
        return v


class PatchDcaPlanPayload(BaseModel):
    name: str | None = None
    amount: str | None = None
    frequency: Literal["daily", "weekly", "biweekly", "monthly"] | None = None
    day_of_week: int | None = None
    day_of_month: int | None = None
    end_date: str | None = None
    is_active: int | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            d = Decimal(v)
        except InvalidOperation:
            raise ValueError("amount must be a valid decimal number")
        if d <= 0:
            raise ValueError("amount must be positive")
        return v


class AddDcaRecordPayload(BaseModel):
    scheduled_date: str
    status: str  # 'success' or 'failed'
    transaction_id: int | None = None
    note: str | None = None


class PatchDcaRecordPayload(BaseModel):
    status: str | None = None
    transaction_id: int | None = None
    note: str | None = None
