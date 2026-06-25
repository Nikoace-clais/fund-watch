"""AI fund selection service.

Flow:
  1. fetch_fund_ranking() → raw candidate pool
  2. filter by theme keyword in fund name
  3. take top MAX_CANDIDATES by 1-year return
  4. enrich with max_drawdown (nav_history) + manager/size (detail)
  5. call Claude via tool_use → structured ranked recommendations
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import anthropic
from pydantic import BaseModel

from ..fund_source import fetch_fund_detail, fetch_fund_ranking, fetch_nav_history
from .metrics import max_drawdown

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 10  # ponytail: cap to control downstream fetches + token cost


# ── Pydantic schema for Claude tool output ────────────────────────────────────

class FundRec(BaseModel):
    code: str
    rank: int
    reason: str  # 2-3 sentences in Chinese


class AiSelectResult(BaseModel):
    rankings: list[FundRec]
    summary: str  # overall 100-char Chinese paragraph


# ── Main entry point ─────────────────────────────────────────────────────────

async def select_funds(theme: str, emphasis: str) -> dict[str, Any]:
    """Return AI-ranked fund recommendations for the given theme and emphasis.

    Raises ValueError for missing API key or no candidates.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 未设置，无法调用 AI 选基")

    # ── Step 1: Fetch ranking pool ──────────────────────────────────────────
    ranking = await fetch_fund_ranking(page_size=200)

    # ── Step 2: Filter by theme keyword ────────────────────────────────────
    candidates = [f for f in ranking if theme in f["name"]]
    if not candidates:
        raise ValueError(f"板块「{theme}」无匹配基金，请换一个关键词")

    # Top MAX_CANDIDATES by 1-year return
    candidates.sort(key=lambda f: f.get("one_year_return") or -999, reverse=True)
    candidates = candidates[:MAX_CANDIDATES]

    # ── Step 3: Enrich candidates ───────────────────────────────────────────
    enriched: list[dict[str, Any]] = list(
        await asyncio.gather(*[_enrich(c) for c in candidates])
    )

    # ── Step 4: Build prompt ────────────────────────────────────────────────
    rows = [
        "| 序 | 代码 | 名称 | 近1年% | 近3年% | 最大回撤% | 费率 | 经理 | 规模(亿) |",
        "| -- | ---- | ---- | ------ | ------ | --------- | ---- | ---- | -------- |",
    ]
    for i, c in enumerate(enriched, 1):
        rows.append(
            f"| {i} | {c['code']} | {c['name']} "
            f"| {_fmt(c.get('one_year_return'))} "
            f"| {_fmt(c.get('three_year_return'))} "
            f"| {_fmt(c.get('max_drawdown_pct'))} "
            f"| {c.get('fee') or 'N/A'} "
            f"| {c.get('manager') or 'N/A'} "
            f"| {_fmt(c.get('size'))} |"
        )
    fund_table = "\n".join(rows)

    prompt = (
        f"你是一位专业的A股公募基金研究员。请根据用户需求从以下候选基金中给出排名和投资建议。\n\n"
        f"【用户需求】\n"
        f"- 板块主题：{theme}\n"
        f"- 投资着重点：{emphasis}\n\n"
        f"【候选基金数据】\n{fund_table}\n\n"
        f"【说明】\n"
        f"- 近1年%/近3年%：区间涨幅（越高越好）\n"
        f"- 最大回撤%：历史最大峰谷跌幅（越低越稳健）\n"
        f"- 规模：亿元（适中规模流动性好）\n\n"
        "请按着重点综合评估，用 fund_recommendations 工具输出结构化结果。"
        "每只基金 reason 给出2-3句中文。summary 最后注明「仅供参考，不构成投资建议」。"
    )

    # ── Step 5: Call Claude via tool_use ───────────────────────────────────
    client = anthropic.AsyncAnthropic(api_key=api_key)
    result = await client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        tools=[
            {
                "name": "fund_recommendations",
                "description": "Return ranked fund recommendations with reasoning",
                "input_schema": AiSelectResult.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "fund_recommendations"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_block = next(b for b in result.content if b.type == "tool_use")
    ai_result = AiSelectResult(**tool_block.input)  # type: ignore[arg-type]

    # ── Step 6: Merge ────────────────────────────────────────────────────────
    enriched_by_code = {c["code"]: c for c in enriched}
    recs = []
    for rec in ai_result.rankings:
        c = enriched_by_code.get(rec.code, {})
        recs.append(
            {
                "rank": rec.rank,
                "code": rec.code,
                "name": c.get("name", ""),
                "one_year_return": c.get("one_year_return"),
                "three_year_return": c.get("three_year_return"),
                "max_drawdown": c.get("max_drawdown_pct"),
                "fee": c.get("fee"),
                "manager": c.get("manager"),
                "size": c.get("size"),
                "reason": rec.reason,
            }
        )
    recs.sort(key=lambda r: r["rank"])

    return {"summary": ai_result.summary, "recommendations": recs}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enrich(candidate: dict[str, Any]) -> dict[str, Any]:
    code = candidate["code"]
    result: dict[str, Any] = dict(candidate)
    try:
        nav_hist = await fetch_nav_history(code, limit=365)
        nav_values = [h["nav"] for h in nav_hist if h.get("nav") is not None]
        result["max_drawdown_pct"] = max_drawdown(nav_values)
    except Exception:
        logger.warning("nav_history fetch failed for %s", code)
        result["max_drawdown_pct"] = None
    try:
        detail = await fetch_fund_detail(code)
        result["manager"] = detail.get("manager")
        result["size"] = detail.get("size")
        result["fee"] = detail.get("subscription_rate_discounted")
    except Exception:
        logger.warning("fund_detail fetch failed for %s", code)
    return result


def _fmt(v: Any) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)
