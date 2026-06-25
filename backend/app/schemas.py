"""Request payload models."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


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


class AiSelectPayload(BaseModel):
    theme: str
    emphasis: str
    provider: str = "anthropic"  # "anthropic" | "openai"
    api_key: str | None = None   # falls back to ANTHROPIC_API_KEY env var if omitted
    base_url: str | None = None  # openai-compatible endpoint, e.g. https://api.openai.com/v1
    model: str | None = None     # e.g. "gpt-4o"; omit to use per-provider default
