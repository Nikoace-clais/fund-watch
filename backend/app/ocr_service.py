"""Screenshot recognition: PaddleOCR extracts text, text AI parses JSON."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

# ponytail: disable oneDNN — causes RuntimeError: std::exception on WSL2 / some CPUs
#os.environ.setdefault("FLAGS_use_mkldnn", "0")

log = logging.getLogger(__name__)

# ── PaddleOCR engine singleton (non-thread-safe; guard with lock) ─────────────

_ocr_engine: Any = None
_ocr_lock = threading.Lock()


def _get_ocr() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR  # lazy import — heavy startup

        # ponytail: minimal config; limit_side_len default 960 may blur long
        # screenshots → upgrade path is to slice by height (see git history for
        # the old rapidocr _SLICE_* approach) if small text gets missed.
        _ocr_engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _ocr_engine


def warm_up() -> None:
    """Start OCR model download/init in a daemon thread at server startup."""
    threading.Thread(target=_get_ocr, daemon=True).start()


def is_ready() -> bool:
    return _ocr_engine is not None


def ocr_text(image_path: Path) -> str:
    """Extract all text lines from image via PaddleOCR (synchronous, CPU-heavy).

    Call this via run_in_threadpool — PaddleOCR is not thread-safe.
    """
    with _ocr_lock:
        result = _get_ocr().predict(str(image_path))

    lines: list[str] = []
    for res in result:
        texts = res.get("rec_texts") or []
        lines.extend(str(t) for t in texts)
    return "\n".join(lines)


# ── JSON parse (strips markdown fences; finds first balanced block) ───────────


def _parse_json(s: str) -> Any:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = s.find(opener)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(s[start:], start):
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"模型返回了无法解析的 JSON: {s[:120]}")


# ── Text AI call ─────────────────────────────────────────────────────────────


async def _text_json(
    text: str,
    prompt: str,
    *,
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str | None,
) -> Any:
    """Send OCR text + prompt to a text model; return parsed JSON."""
    user_msg = f"{prompt}\n\n---\n{text}"

    if provider == "anthropic":
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=model or "claude-opus-4-8",
            max_tokens=2048,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text
    else:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model or "gpt-4o",
            max_tokens=2048,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.choices[0].message.content or ""

    log.debug("AI raw response (%s chars): %s", len(raw), raw[:300])
    try:
        return _parse_json(raw)
    except ValueError:
        log.warning("AI returned non-JSON (provider=%s model=%s): %r", provider, model, raw)
        raise


# ── Prompts ──────────────────────────────────────────────────────────────────

_FUND_PROMPT = """\
以下是从基金 App 截图经 OCR 识别出的文字，
可能有顺序错乱或个别字符识别错误，请据此提取所有基金信息。

仅输出 JSON 对象，不要输出任何解释、说明或其他文字。

格式：{"funds":[{"code":"6位数字基金代码或null","name":"基金名称或null","amount":持有金额数字或null}]}

规则：
- code 若截图中有 6 位纯数字代码则填写，否则填 null（支付宝等 App 不显示代码）
- name 尽量完整，识别不到则填 null
- amount 为持有金额数字（如 1234.56），识别不到则填 null
- 有 name 但无 code 的条目也必须包含，不要过滤
- 若文字中无基金信息，返回 {"funds":[]}\
"""

_TX_PROMPT = """\
以下是从基金交易截图经 OCR 识别出的文字，
可能有顺序错乱或个别字符识别错误，请据此提取交易记录。

仅输出 JSON 对象，不要输出任何解释、说明或其他文字。

格式：{"direction":"buy|sell|null","code":"6位基金代码或null","trade_date":"YYYY-MM-DD或null","nav":"净值数字字符串或null","shares":"份额数字字符串或null","amount":"金额数字字符串或null"}

规则：
- direction：买入/申购/定投/认购 → "buy"，卖出/赎回/转出 → "sell"，识别不到 → null
- code 必须是 6 位纯数字，识别不到则 null
- 识别不到的字段填 null\
"""


# ── Public API ───────────────────────────────────────────────────────────────


async def extract_funds_from_text(
    text: str,
    cfg: dict[str, Any],
) -> list[dict]:
    """Return [{code, name, amount}] parsed from OCR text.

    code is "" for name-only entries (e.g. Alipay screenshots without codes).
    """
    log.info("OCR文本(%d字符):\n%s", len(text), text)
    try:
        result = await _text_json(
            text,
            _FUND_PROMPT,
            provider=cfg["provider"],
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url"),
            model=cfg.get("model"),
        )
    except ValueError:
        log.warning("AI返回非JSON，按空处理")
        return []
    # Accept both {"funds": [...]} wrapper (json_object mode) and bare array (legacy)
    if isinstance(result, dict):
        result = result.get("funds") or []
    if not isinstance(result, list):
        return []
    out = []
    for item in result:
        raw_code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        code = raw_code if (len(raw_code) == 6 and raw_code.isdigit()) else ""
        if not code and not name:
            continue
        out.append({"code": code, "name": name, "amount": item.get("amount")})

    with_code = [x for x in out if x["code"]]
    name_only = [x for x in out if not x["code"]]
    log.info(
        "AI提取: 共%d条 有代码%d条 仅名称%d条 → %s",
        len(out),
        len(with_code),
        len(name_only),
        [(x["code"] or f"名称:{x['name'][:8]}") for x in out],
    )
    return out


async def extract_transaction_from_text(
    text: str,
    cfg: dict[str, Any],
) -> tuple[str, dict]:
    """Return (raw_json_str, tx_dict) parsed from OCR text."""
    result = await _text_json(
        text,
        _TX_PROMPT,
        provider=cfg["provider"],
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        model=cfg.get("model"),
    )
    raw_text = json.dumps(result, ensure_ascii=False)
    tx: dict[str, Any] = {
        "direction": None,
        "code": None,
        "trade_date": None,
        "nav": None,
        "shares": None,
        "amount": None,
    }
    if isinstance(result, dict):
        for key in tx:
            v = result.get(key)
            if v not in (None, "null", ""):
                tx[key] = v
    return raw_text, tx


# ── Stage 1.5: Pro model identifies unmatched fund names ─────────────────────

_IDENTIFY_PROMPT = """\
以下是从基金 App 截图 OCR 识别出的文字，以及系统未能搜索到的基金名称片段。

请根据 OCR 原文推断每条名称对应的完整基金信息。

仅输出 JSON，不要输出任何解释。

格式：{"items":[{"index":序号,"full_name":"完整基金中文名称或null","code":"6位数字基金代码或null"}]}

规则：
- full_name 输出完整官方基金名称（如「招商中证白酒指数(LOF)A」）
- code 输出 6 位纯数字基金代码（如「161725」），不确定则填 null
- 若 OCR 原文中完全找不到对应基金，full_name 和 code 均填 null
- 不确定份额(A/C/D)时，优先选 A 份额\
"""


async def resolve_unknown_fund_names(
    ocr_text: str,
    unknown: list[dict],
    cfg: dict[str, Any],
) -> dict[int, dict]:
    """Ask Pro model to identify fund name + code for OCR names with no search hit.

    unknown items: {index, name}
    Returns {index: {full_name, code}} — code may be None.
    """
    review_model = cfg.get("review_model") or cfg.get("model")
    if not review_model or not cfg.get("api_key"):
        log.info("跳过未命中识别: 未配置review_model")
        return {}

    lines = ["OCR原文：", ocr_text, "", "未命中的基金名称片段："]
    for item in unknown:
        lines.append(f"#{item['index']} 「{item['name']}」")
    user_content = "\n".join(lines)

    log.info("Pro未命中识别: %d条 → %s", len(unknown), [x["name"] for x in unknown])
    try:
        result = await _text_json(
            user_content,
            _IDENTIFY_PROMPT,
            provider=cfg["provider"],
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url"),
            model=review_model,
        )
    except Exception as exc:
        log.warning("Pro未命中识别失败(%s)", exc)
        return {}

    out: dict[int, dict] = {}
    for item in (result.get("items") or [] if isinstance(result, dict) else []):
        idx = item.get("index")
        name = (item.get("full_name") or "").strip()
        raw_code = str(item.get("code") or "").strip()
        code = raw_code if (len(raw_code) == 6 and raw_code.isdigit()) else None
        if idx is not None and name:
            ocr_name = unknown[idx]["name"] if isinstance(idx, int) and idx < len(unknown) else "?"
            log.info("Pro识别 #%d: 「%s」→ 名称=「%s」代码=%s", idx, ocr_name, name, code or "未知")
            out[idx] = {"full_name": name, "code": code}
    return out


# ── Stage 2: Pro model review ────────────────────────────────────────────────

_REVIEW_PROMPT = """\
你是基金信息核查员。以下是从 App 截图 OCR 识别出的文字，以及系统对每条基金的初步匹配结果。

请逐条判断：初步匹配的基金是否就是截图里描述的那只基金？

仅输出 JSON，不要输出任何解释。

格式：{"reviews":[{"index":序号,"ok":true或false,"corrected_name":"若错误则给出正确基金全名，否则null"}]}

规则：
- ok=true：匹配正确，corrected_name 填 null
- ok=false：匹配错误，corrected_name 填正确基金的**完整中文名称**（不要输出代码，不要输出英文缩写）
- 若截图文字不足以判断，填 ok=true（保守策略，不要过度纠正）
- corrected_name 只输出基金全名，例如「招商中证白酒指数（LOF）A」\
"""


async def review_fund_matches(
    ocr_text: str,
    preliminary: list[dict],
    cfg: dict[str, Any],
) -> list[dict]:
    """Stage 2: Pro model verifies preliminary matches and corrects wrong ones.

    preliminary items: {index, ocr_name, code, name, ...}
    Returns updated list with 'review' field: 'confirmed'|'corrected'|'unreviewed'.
    """
    if not preliminary:
        return preliminary

    review_model = cfg.get("review_model") or cfg.get("model")
    if not review_model or not cfg.get("api_key"):
        log.info("跳过Pro核对: 未配置review_model或api_key")
        for item in preliminary:
            item["review"] = "unreviewed"
        return preliminary

    # Build numbered list for the model
    lines = ["OCR原文：", ocr_text, "", "初步匹配结果："]
    for item in preliminary:
        lines.append(
            f"#{item['index']} OCR识别名称:「{item['ocr_name']}」→ 匹配为:「{item['name']}」({item['code']})"
        )
    user_content = "\n".join(lines)

    log.info("Pro核对: 发送%d条给模型 %s", len(preliminary), review_model)
    try:
        result = await _text_json(
            user_content,
            _REVIEW_PROMPT,
            provider=cfg["provider"],
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url"),
            model=review_model,
        )
    except Exception as exc:
        log.warning("Pro核对调用失败(%s)，跳过", exc)
        for item in preliminary:
            item["review"] = "unreviewed"
        return preliminary

    reviews: list[dict] = []
    if isinstance(result, dict):
        reviews = result.get("reviews") or []

    idx_map = {item["index"]: item for item in preliminary}
    for rv in reviews:
        idx = rv.get("index")
        item = idx_map.get(idx)
        if item is None:
            continue
        if rv.get("ok"):
            item["review"] = "confirmed"
            log.info("Pro核对 #%d: ✓ 确认「%s」(%s)", idx, item["name"], item["code"])
        else:
            corrected = (rv.get("corrected_name") or "").strip()
            if corrected:
                item["review"] = "corrected"
                item["corrected_name"] = corrected
                log.info(
                    "Pro核对 #%d: ✗ 「%s」(%s) → 纠正为「%s」(待搜索)",
                    idx, item["name"], item["code"], corrected,
                )
            else:
                item["review"] = "confirmed"  # no correction offered → keep
    # Fill any not returned by model
    for item in preliminary:
        if "review" not in item:
            item["review"] = "unreviewed"
    return preliminary
