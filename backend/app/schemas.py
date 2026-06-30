"""Request payload models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


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
    portfolio_id: int | None = None      # attach to existing portfolio
    portfolio_name: str | None = None    # or create a new one with this name


class AddTransactionPayload(BaseModel):
    direction: str  # 'buy' or 'sell'
    trade_date: str
    nav: str
    shares: str
    fee: str = "0"
    note: str | None = None
    source: str = "manual"
    portfolio_id: int | None = None


class AiSelectPayload(BaseModel):
    theme: str
    emphasis: str
    provider: str = "anthropic"  # "anthropic" | "openai"
    api_key: str | None = None  # falls back to ANTHROPIC_API_KEY env var if omitted
    base_url: str | None = (
        None  # openai-compatible endpoint, e.g. https://api.openai.com/v1
    )
    model: str | None = (
        None  # e.g. "deepseek-v4-flash"; omit to use per-provider default
    )
    analysis_model: str | None = (
        None  # e.g. "deepseek-v4-pro"; falls back to model when omitted
    )
