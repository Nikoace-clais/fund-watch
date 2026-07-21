"""Shared constants and helpers used across routers and services."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, TypeVar, overload

from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .repositories import portfolios_repo

T = TypeVar("T")

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

CENT = Decimal("0.01")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"

# LLM provider 缺省模型（make_llm_client 的两条分支各自使用）
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"

# ASCII-only digits: str.isdigit() also accepts non-decimal Unicode "digit"
# characters (e.g. superscripts) that aren't valid fund/stock codes.
_CODE_RE = re.compile(r"^[0-9]{6}$")

# YYYY-MM-DD 补零规范格式（入库后按字符串比较日期）；真实日历校验靠 strptime
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_code(code: str) -> bool:
    """True if code is a bare 6-digit fund/stock code (no whitespace stripping)."""
    return bool(code) and bool(_CODE_RE.match(code))


def q2(x: Decimal) -> Decimal:
    """量化到分（两位小数）；金额/收益率的统一取舍入口。"""
    return x.quantize(CENT)


def is_valid_date(s: str) -> bool:
    """True if s 是合法的 YYYY-MM-DD 日期（格式补零规范且为真实日历日期）。"""
    if not _DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate_date(s: str, field: str = "date") -> str:
    """路由层日期校验：非法抛 400，合法原样返回。"""
    if not is_valid_date(s):
        raise HTTPException(
            status_code=400, detail=f"{field} 必须是有效的 YYYY-MM-DD 日期"
        )
    return s


def utc_now_iso() -> str:
    """当前 UTC 时间的 ISO 字符串；入库时间戳的统一入口。"""
    return datetime.now(timezone.utc).isoformat()


@overload
async def safe_await(
    coro: Awaitable[T], default: None = None, *, log: str | None = None
) -> T | None: ...
@overload
async def safe_await(
    coro: Awaitable[T], default: T, *, log: str | None = None
) -> T: ...
async def safe_await(
    coro: Awaitable[T], default: T | None = None, *, log: str | None = None
) -> T | None:
    """「失败记日志返回默认值」样板：异常时按 log 文案记 warning 并返回 default。"""
    try:
        return await coro
    except Exception as exc:
        if log is not None:
            logger.warning("%s: %s", log, exc)
        return default


def sse_response(gen: AsyncGenerator[str, None]) -> StreamingResponse:
    """SSE 流式响应统一封装（禁缓存、禁 nginx 缓冲）。"""
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def read_upload_limited(
    file: UploadFile, max_bytes: int, err_detail: str
) -> bytes:
    """限量读取上传文件内容：超过 max_bytes 抛 400(err_detail)。"""
    data = await file.read(max_bytes + 1)  # 限量读取，超出即判过大
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=err_detail)
    return data


def make_llm_client(provider: str, api_key: str, base_url: str | None = None) -> Any:
    """按 provider 构造异步 LLM 客户端（openai 兼容 / anthropic）。

    SDK 导入放在函数内：core 被所有模块引用，避免启动时无条件加载两个 SDK。
    """
    if provider == "anthropic":
        import anthropic

        return anthropic.AsyncAnthropic(api_key=api_key)
    import openai

    return openai.AsyncOpenAI(api_key=api_key, base_url=base_url)


def validate_code(code: str) -> str:
    code = code.strip()
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="fund code must be 6 digits")
    return code


def resolve_portfolio(conn: sqlite3.Connection, portfolio_id: int | None) -> int:
    """Return portfolio_id, defaulting to the first portfolio if none given."""
    if portfolio_id is not None:
        if not portfolios_repo.exists(conn, portfolio_id):
            raise HTTPException(status_code=404, detail="组合不存在")
        return portfolio_id
    first_id = portfolios_repo.first_id(conn)
    if first_id is None:
        raise HTTPException(status_code=404, detail="尚无组合，请先导入基金建立组合")
    return first_id


async def fetch_502(coro: Awaitable[T]) -> T:
    """Await an upstream fetch, mapping any failure to HTTP 502.

    异常细节只记服务端日志，不回传前端（可能含内部地址/参数）。
    """
    try:
        return await coro
    except Exception as exc:
        logger.warning("上游数据源请求失败: %s", exc)
        raise HTTPException(
            status_code=502, detail="上游数据源请求失败，请稍后重试"
        ) from exc


def sse(obj: dict[str, Any]) -> str:
    """Format one SSE data frame."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def extract_json(s: str) -> Any:
    """Parse model output as JSON.

    Strips markdown fences; tolerates prefix/suffix text around the first
    balanced JSON array/object (thinking models often emit trailing prose).
    """
    s = s.strip()
    if not s:
        raise ValueError("模型返回空响应")
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    decoder = json.JSONDecoder()
    starts = [0] + sorted(i for i in (s.find("["), s.find("{")) if i > 0)
    for start in starts:
        try:
            return decoder.raw_decode(s, start)[0]
        except json.JSONDecodeError:
            continue
    raise ValueError(f"模型返回了无法解析的 JSON: {s[:120]}")
