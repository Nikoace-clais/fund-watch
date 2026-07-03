"""AI agentic fund selection — dual-model agentic loop with SSE streaming.

Three phases:
  1. Orchestration loop (model / Flash, ≤ MAX_ROUNDS):
       search_funds / get_fund_metrics / finish_research
       Only collects data into store; does NOT produce rankings.
  2. Analysis (analysis_model / Pro, single call):
       fund_recommendations — ranks candidates from store data.
  3. Review (analysis_model / Pro, single call):
       fund_recommendations — consistency check against emphasis.

analysis_model defaults to model when not supplied (single-model fallback).
Each tool call boundary yields an SSE "step" event.
Final output yields an SSE "result" event. Errors yield "error".
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import anthropic
import openai

from ..fund_source import fetch_fund_detail, fetch_fund_ranking, fetch_nav_history

logger = logging.getLogger(__name__)


def max_drawdown(nav_list: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a positive percentage.

    Example: 32.5 means -32.5% from peak. Returns 0.0 if fewer than 2 points.
    """
    if len(nav_list) < 2:
        return 0.0
    peak = nav_list[0]
    max_dd = 0.0
    for v in nav_list:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)

MAX_ROUNDS = 6
_MAX_SEARCH = 15  # ponytail: cap candidates per search call
_THEME_FUND_TYPE: dict[str, str] = {"QDII": "qdii", "债": "zq", "货币": "hb"}


# ── Unified tool call ─────────────────────────────────────────────────────────


@dataclass
class _TC:
    id: str
    name: str
    args: dict[str, Any]


# ── Tool implementations ──────────────────────────────────────────────────────


async def _search(theme: str, fund_type: str = "") -> dict[str, Any]:
    ft = fund_type or _THEME_FUND_TYPE.get(theme, "gp")
    ranking = await fetch_fund_ranking(fund_type=ft, page_size=200)
    if theme not in _THEME_FUND_TYPE:
        ranking = [f for f in ranking if theme in f["name"]]
    ranking.sort(key=lambda f: f.get("one_year_return") or -999, reverse=True)
    top = ranking[:_MAX_SEARCH]
    return {
        "candidates": [
            {
                "code": f["code"],
                "name": f["name"],
                "one_year_return": f.get("one_year_return"),
                "three_year_return": f.get("three_year_return"),
            }
            for f in top
        ],
        "count": len(top),
    }


async def _metrics(code: str) -> dict[str, Any]:
    r: dict[str, Any] = {"code": code}
    try:
        hist = await fetch_nav_history(code, limit=365)
        navs = [h["nav"] for h in hist if h.get("nav") is not None]
        r["max_drawdown_pct"] = max_drawdown(navs)
    except Exception:
        logger.warning("nav_history failed for %s", code)
        r["max_drawdown_pct"] = None
    try:
        detail = await fetch_fund_detail(code)
        r.update(
            {
                "manager": detail.get("manager"),
                "size": detail.get("size"),
                "fee": detail.get("subscription_rate_discounted"),
            }
        )
    except Exception:
        logger.warning("fund_detail failed for %s", code)
    return r


async def _dispatch(tc: _TC, store: dict[str, dict[str, Any]]) -> Any:
    """Execute a tool call and update the shared data store."""
    if tc.name == "search_funds":
        result = await _search(**tc.args)
        for c in result.get("candidates", []):
            store.setdefault(c["code"], {}).update(c)
        return result
    if tc.name == "get_fund_metrics":
        result = await _metrics(**tc.args)
        store.setdefault(tc.args["code"], {}).update(result)
        return result
    if tc.name in ("finish_research", "fund_recommendations"):
        return tc.args  # pass-through; signals phase end
    return {"error": f"unknown tool: {tc.name}"}


# ── Merge LLM rankings with accumulated store ─────────────────────────────────


def _merge(rankings: list[dict], store: dict[str, dict]) -> list[dict]:
    recs = []
    for r in rankings:
        m = store.get(r["code"], {})
        recs.append(
            {
                "rank": r.get("rank", 0),
                "code": r["code"],
                "name": m.get("name", ""),
                "one_year_return": m.get("one_year_return"),
                "three_year_return": m.get("three_year_return"),
                "max_drawdown": m.get("max_drawdown_pct"),
                "fee": m.get("fee"),
                "manager": m.get("manager"),
                "size": m.get("size"),
                "reason": r.get("reason", ""),
            }
        )
    recs.sort(key=lambda x: x["rank"])
    return recs


def _store_to_table(store: dict[str, dict[str, Any]]) -> str:
    """Render collected fund data as a markdown table for the analysis prompt."""

    def fmt(v: Any) -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    rows = [
        "| 序 | 代码 | 名称 | 近1年% | 近3年% | 最大回撤% | 费率 | 经理 | 规模(亿) |",
        "| -- | ---- | ---- | ------ | ------ | --------- | ---- | ---- | -------- |",
    ]
    for i, (code, m) in enumerate(store.items(), 1):
        rows.append(
            f"| {i} | {code} | {m.get('name', '')} "
            f"| {fmt(m.get('one_year_return'))} "
            f"| {fmt(m.get('three_year_return'))} "
            f"| {fmt(m.get('max_drawdown_pct'))} "
            f"| {m.get('fee') or 'N/A'} "
            f"| {m.get('manager') or 'N/A'} "
            f"| {fmt(m.get('size'))} |"
        )
    return "\n".join(rows)


# ── SSE helpers ───────────────────────────────────────────────────────────────


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _step(text: str) -> str:
    return _sse({"type": "step", "text": text})


def _result(data: dict[str, Any]) -> str:
    return _sse({"type": "result", "data": data})


def _err(text: str) -> str:
    return _sse({"type": "error", "text": text})


def _step_text(tc: _TC, res: Any) -> str:
    if tc.name == "search_funds":
        n = res.get("count", 0) if isinstance(res, dict) else 0
        return f"搜索「{tc.args.get('theme', '')}」板块，找到 {n} 只候选"
    if tc.name == "get_fund_metrics":
        return f"获取 {tc.args.get('code', '')} 的历史表现与经理数据"
    if tc.name == "finish_research":
        return "数据收集完成，开始深度分析…"
    if tc.name == "fund_recommendations":
        n = len(res.get("rankings", [])) if isinstance(res, dict) else 0
        return f"生成 {n} 只基金推荐，进入审核"
    return tc.name


# ── Tool schemas ──────────────────────────────────────────────────────────────

_P_SEARCH: dict[str, Any] = {
    "type": "object",
    "properties": {
        "theme": {
            "type": "string",
            "description": "板块关键词，如「半导体」「医药」「QDII」",
        },
        "fund_type": {
            "type": "string",
            "description": "eastmoney ft: gp/hh/zq/qdii，留空自动判断",
        },
    },
    "required": ["theme"],
}
_P_METRICS: dict[str, Any] = {
    "type": "object",
    "properties": {"code": {"type": "string", "description": "6位基金代码"}},
    "required": ["code"],
}
_P_FINISH: dict[str, Any] = {
    "type": "object",
    "properties": {"note": {"type": "string", "description": "可选：说明收集情况"}},
}
_P_REC: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rankings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "rank": {"type": "integer"},
                    "reason": {"type": "string", "description": "2-3句中文投资理由"},
                },
                "required": ["code", "rank", "reason"],
            },
        },
        "summary": {
            "type": "string",
            "description": "100字内总结，末尾注「仅供参考，不构成投资建议」",
        },
    },
    "required": ["rankings", "summary"],
}


def _oai_tool(name: str, desc: str, params: dict) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": name, "description": desc, "parameters": params},
    }


def _ant_tool(name: str, desc: str, params: dict) -> dict[str, Any]:
    return {"name": name, "description": desc, "input_schema": params}


# Phase 1 orchestration tools (no fund_recommendations — ranking is NOT done here)
_ORCH_DEFS = [
    ("search_funds", "搜索板块候选基金，返回代码/名称/近1年收益", _P_SEARCH),
    ("get_fund_metrics", "获取单只基金的最大回撤、经理、规模、费率", _P_METRICS),
    ("finish_research", "数据收集完成，结束收集阶段", _P_FINISH),
]
_ORCH_OAI: list[dict[str, Any]] = [_oai_tool(*t) for t in _ORCH_DEFS]
_ORCH_ANT: list[dict[str, Any]] = [_ant_tool(*t) for t in _ORCH_DEFS]

# Phase 2/3 analysis tools (ranking only)
_ANALYSIS_OAI: list[dict[str, Any]] = [
    _oai_tool("fund_recommendations", "输出排名推荐结果", _P_REC)
]
_ANALYSIS_ANT: list[dict[str, Any]] = [
    _ant_tool("fund_recommendations", "输出排名推荐结果", _P_REC)
]


# ── Argument parse (tolerates trailing content from thinking models) ───────────


def _parse(raw: str) -> dict[str, Any]:
    s = raw.strip()
    try:
        obj, _ = json.JSONDecoder().raw_decode(s)
        return obj
    except json.JSONDecodeError:
        # Fallback: extract first balanced {...} block (handles mid-string corruption)
        depth = 0
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[: i + 1])
                    except json.JSONDecodeError:
                        break
        raise ValueError(f"模型返回了无法解析的 JSON: {s[:120]}")


# ── LLM call helpers ──────────────────────────────────────────────────────────


async def _call_oai(
    messages: list,
    tools: list,
    api_key: str,
    base_url: str | None,
    model: str | None,
) -> tuple[dict[str, Any], list[_TC]]:
    kw: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kw["base_url"] = base_url
    client = openai.AsyncOpenAI(**kw)
    resp = await client.chat.completions.create(
        model=model or "gpt-4o",
        max_tokens=8192,
        tools=tools,
        messages=messages,
    )
    msg = resp.choices[0].message
    u = resp.usage
    logger.debug(
        "[oai] cache_hit=%s cache_miss=%s output=%s content=%s tool_calls=%s",
        getattr(u, "prompt_cache_hit_tokens", None),
        getattr(u, "prompt_cache_miss_tokens", None),
        u.completion_tokens if u else None,
        msg.content,
        [tc.function.name for tc in (msg.tool_calls or [])],
    )
    tcs = [
        _TC(id=tc.id, name=tc.function.name, args=_parse(tc.function.arguments))
        for tc in (msg.tool_calls or [])
    ]
    asst: dict[str, Any] = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        asst["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return asst, tcs


async def _call_ant(
    messages: list,
    tools: list,
    api_key: str,
    model: str | None,
    system: str | None = None,
) -> tuple[Any, list[_TC]]:
    client = anthropic.AsyncAnthropic(api_key=api_key)
    kw: dict[str, Any] = {
        "model": model or "claude-opus-4-8",
        "max_tokens": 8192,
        "tools": tools,
        "messages": messages,
    }
    if system:
        kw["system"] = system
    resp = await client.messages.create(**kw)
    logger.debug("[ant] stop_reason=%s content=%s", resp.stop_reason, resp.content)
    tcs = [
        _TC(id=b.id, name=b.name, args=dict(b.input))
        for b in resp.content
        if b.type == "tool_use"
    ]
    return resp.content, tcs


def _append_oai(messages: list, asst: dict, tcs: list[_TC], results: list) -> list:
    messages.append(asst)
    for tc, r in zip(tcs, results):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(r, ensure_ascii=False),
            }
        )
    return messages


def _append_ant(messages: list, content: Any, tcs: list[_TC], results: list) -> list:
    messages.append({"role": "assistant", "content": content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(r, ensure_ascii=False),
                }
                for tc, r in zip(tcs, results)
            ],
        }
    )
    return messages


# ── Prompts ───────────────────────────────────────────────────────────────────


def _system_orch(theme: str, emphasis: str) -> str:
    return (
        "你是一位专业的A股公募基金研究助手，负责数据收集。\n"
        f"用户需要「{theme}」板块、着重「{emphasis}」的基金推荐。\n\n"
        "工具使用规范：\n"
        f"1. 先调用 search_funds 找候选基金"
        f"（theme 只能是「{theme}」，禁止搜索其他板块）；\n"
        "2. 对最值得关注的候选逐一调用 get_fund_metrics 获取详细指标；\n"
        "3. 收集足够数据后，调用 finish_research 结束收集阶段。\n"
        "注意：你只负责数据收集，最终排名由专门的分析模型完成。"
    )


def _user_orch(theme: str, emphasis: str) -> str:
    return f"请收集「{theme}」板块中着重「{emphasis}」方向的候选基金数据。"


def _system_analysis(theme: str, emphasis: str) -> str:
    return (
        "你是一位专业的A股公募基金研究员。\n"
        f"用户需要「{theme}」板块、着重「{emphasis}」的基金推荐。\n\n"
        "以下是已收集的候选基金完整数据，"
        "请综合评估后调用 fund_recommendations 输出前5名排名。\n"
        "- 近1年%/近3年%：区间涨幅（越高越好）\n"
        "- 最大回撤%：历史峰谷跌幅（越低越稳健）\n"
        "- 规模：亿元（适中规模流动性好）\n\n"
        "每只基金 reason 给出2-3句中文理由，说明为何符合用户着重点。\n"
        "summary 末尾注明「仅供参考，不构成投资建议」。"
    )


def _user_analysis(table: str, theme: str, emphasis: str) -> str:
    return (
        f"请从以下「{theme}」板块候选基金中，按「{emphasis}」着重点排出前5名：\n\n"
        f"{table}"
    )


def _review_msg(initial: dict[str, Any]) -> str:
    return (
        "以下是初步推荐结果，请核查排名是否与用户着重点一致。"
        "若发现明显矛盾（例如强调稳健但推荐了高回撤基金），请调整排名或 reason。"
        "无需再调用其他工具，直接用 fund_recommendations 输出最终结果。\n\n"
        + json.dumps(initial, ensure_ascii=False, indent=2)
    )


# ── One-shot LLM call (phases 2 & 3 share this pattern) ──────────────────────


async def _single_call(
    system: str,
    user: str,
    tools: list,
    is_oai: bool,
    api_key: str,
    base_url: str | None,
    model: str | None,
) -> list[_TC]:
    if is_oai:
        msgs: list[Any] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        _, tcs = await _call_oai(msgs, tools, api_key, base_url, model)
    else:
        msgs = [{"role": "user", "content": user}]
        _, tcs = await _call_ant(msgs, tools, api_key, model, system=system)
    return tcs


# ── Main entry point ──────────────────────────────────────────────────────────


async def agent_loop(
    theme: str,
    emphasis: str,
    provider: str = "anthropic",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    analysis_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted strings.

    Never raises — yields error event on failure.
    """
    if not api_key and provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        yield _err("未配置 API Key，请在「AI 配置」中填写")
        return

    try:
        async for event in _agent_loop_inner(
            theme, emphasis, provider, api_key, base_url, model, analysis_model
        ):
            yield event
    except Exception as exc:
        logger.exception("agent_loop unhandled error")
        yield _err(f"AI 分析出错：{exc}")


async def _agent_loop_inner(
    theme: str,
    emphasis: str,
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str | None,
    analysis_model: str | None,
) -> AsyncGenerator[str, None]:
    is_oai = provider != "anthropic"
    # ponytail: analysis_model falls back to model (single-model when not configured)
    a_model = analysis_model or model
    orch_tools = _ORCH_OAI if is_oai else _ORCH_ANT
    anlys_tools = _ANALYSIS_OAI if is_oai else _ANALYSIS_ANT
    orch_sys = _system_orch(theme, emphasis)
    store: dict[str, dict[str, Any]] = {}

    # ── Phase 1: Orchestration loop (model / Flash) ───────────────────────────
    if is_oai:
        messages: list[Any] = [
            {"role": "system", "content": orch_sys},
            {"role": "user", "content": _user_orch(theme, emphasis)},
        ]
    else:
        messages = [{"role": "user", "content": _user_orch(theme, emphasis)}]

    for _ in range(MAX_ROUNDS):
        asst: dict[str, Any] = {}
        content: Any = None
        if is_oai:
            asst, tcs = await _call_oai(messages, orch_tools, api_key, base_url, model)
        else:
            content, tcs = await _call_ant(
                messages, orch_tools, api_key, model, system=orch_sys
            )

        if not tcs:
            yield _err(
                "模型未调用工具，请换用支持工具调用的模型（如 deepseek-v4-flash）"
            )
            return

        # Lock theme to user's selection — LLM must not search other sectors
        for tc in tcs:
            if tc.name == "search_funds":
                tc.args["theme"] = theme
        results = await asyncio.gather(*[_dispatch(tc, store) for tc in tcs])

        finished = False
        for tc, res in zip(tcs, results):
            yield _step(_step_text(tc, res))
            if tc.name == "finish_research":
                finished = True
                break

        if finished:
            break

        if is_oai:
            _append_oai(messages, asst, tcs, list(results))
        else:
            _append_ant(messages, content, tcs, list(results))
    # MAX_ROUNDS exceeded → fall through with whatever store has

    if not store:
        yield _err("未收集到任何基金数据，请重试")
        return

    # ── Phase 2: Analysis (analysis_model / Pro) ──────────────────────────────
    yield _step("AI 正在分析排名…")

    table = _store_to_table(store)
    anlys_sys = _system_analysis(theme, emphasis)
    anlys_user = _user_analysis(table, theme, emphasis)
    anlys_tcs = await _single_call(
        anlys_sys, anlys_user, anlys_tools, is_oai, api_key, base_url, a_model
    )

    initial_args: dict[str, Any] = {}
    for tc in anlys_tcs:
        if tc.name == "fund_recommendations":
            initial_args = tc.args
            break

    if not initial_args:
        yield _err("分析模型未返回排名结果，请重试")
        return

    # ── Phase 3: Review (analysis_model / Pro) ────────────────────────────────
    # ponytail: independent Review is a second Pro call (costs more); to reduce cost
    # merge review requirements into Phase 2 system prompt and remove Phase 3.
    # Kept because user explicitly requested an independent review step.
    yield _step("AI 正在审核推荐结果…")

    merged_initial = _merge(initial_args.get("rankings", []), store)
    initial_data: dict[str, Any] = {
        "summary": initial_args.get("summary", ""),
        "recommendations": merged_initial,
    }
    rev_sys = "你是基金推荐审核员，核查排名与用户着重点的一致性后输出最终结果。"
    rev_tcs = await _single_call(
        rev_sys,
        _review_msg(initial_data),
        anlys_tools,
        is_oai,
        api_key,
        base_url,
        a_model,
    )

    for tc in rev_tcs:
        if tc.name == "fund_recommendations":
            final = _merge(tc.args.get("rankings", []), store)
            yield _result(
                {"summary": tc.args.get("summary", ""), "recommendations": final}
            )
            return

    # Reviewer skipped tool call — return Phase 2 result as-is
    yield _result(initial_data)
