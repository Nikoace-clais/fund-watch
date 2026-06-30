"""Screenshot recognition endpoints (PaddleOCR → text AI)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ..core import UPLOAD_DIR
from ..db import get_conn
from ..fund_source import search_fund_by_name
from ..ocr_service import (
    extract_funds_from_text,
    extract_transaction_from_text,
    is_ready,
    ocr_text,
    resolve_unknown_fund_names,
    review_fund_matches,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["ocr"])

_VERIFY_LIMIT = 15


@router.get("/api/ocr/status")
async def ocr_status() -> dict:
    return {"ready": is_ready()}


def _unique_upload_path(filename: str | None, prefix: str) -> Path:
    suffix = Path(filename or "upload.png").suffix or ".png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return UPLOAD_DIR / f"{prefix}_{ts}_{uuid4().hex[:8]}{suffix}"


def _build_cfg(
    provider: str,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
    review_model: str | None = None,
) -> dict:
    resolved = (
        api_key
        or (os.environ.get("ANTHROPIC_API_KEY") if provider == "anthropic" else None)
        or ""
    )
    return {
        "provider": provider,
        "api_key": resolved,
        "base_url": base_url,
        "model": model,
        "review_model": review_model or None,
    }


def _ai_error(exc: Exception) -> str:
    msg = str(exc)
    if "authentication" in msg.lower() or "401" in msg:
        return f"API 密钥无效或未配置：{msg}"
    return msg


async def _resolve_code(code: str) -> dict | None:
    """Verify a 6-digit candidate against the fund search source.

    Drops codes the source doesn't recognise (guards against hallucination).
    Falls back to keeping the code when the source itself fails.
    """
    try:
        results = await search_fund_by_name(code, limit=1)
    except Exception:
        return {"code": code, "name": "", "type": None}
    for r in results:
        if r.get("code") == code:
            return {"code": code, "name": r.get("name", ""), "type": r.get("type")}
    return None


def _sse(type_: str, **kwargs: object) -> str:
    return f"data: {json.dumps({'type': type_, **kwargs}, ensure_ascii=False)}\n\n"


async def _ocr_fund_generator(
    files_data: list[tuple[str, bytes]],  # [(filename, bytes), ...]
    cfg: dict,
) -> object:
    """Async generator yielding SSE events for the fund OCR pipeline."""
    all_funds: list[dict] = []
    all_raw_texts: list[str] = []
    seen_keys: set[str] = set()

    # ── OCR ────────────────────────────────────────────────────────────────
    n = len(files_data)
    yield _sse("step", step="ocr", text=f"正在识别图片文字（共 {n} 张）...")
    for filename, data in files_data:
        path = _unique_upload_path(filename, "ocr")
        path.write_bytes(data)
        log.info("OCR处理: %s", filename)
        raw_text: str = await run_in_threadpool(ocr_text, path)
        all_raw_texts.append(raw_text)

        # ── AI extract ───────────────────────────────────────────────────
        yield _sse("step", step="ai_extract", text="AI 提取基金名称...")
        try:
            page_funds = await extract_funds_from_text(raw_text, cfg)
        except Exception as e:
            yield _sse("error", text=_ai_error(e))
            return

        for fund in page_funds:
            key = fund["code"] or fund["name"]
            if key and key not in seen_keys:
                seen_keys.add(key)
                all_funds.append(fund)

    combined_raw = "\n---\n".join(all_raw_texts)

    code_funds = [f for f in all_funds if f["code"]]
    name_funds = [f for f in all_funds if not f["code"]]
    log.info("分类结果: 有代码=%d 仅名称=%d", len(code_funds), len(name_funds))

    # ── Verify code funds ────────────────────────────────────────────────
    matched_funds: list[dict] = []
    codes: list[str] = []
    truncated: list[str] = []
    if code_funds:
        yield _sse(
            "step", step="search", text=f"验证基金代码（{len(code_funds)} 个）..."
        )
        if len(code_funds) > _VERIFY_LIMIT:
            truncated += [f["code"] for f in code_funds[_VERIFY_LIMIT:]]
        infos = await asyncio.gather(
            *[_resolve_code(f["code"]) for f in code_funds[:_VERIFY_LIMIT]]
        )
        for item, info in zip(code_funds[:_VERIFY_LIMIT], infos):
            if info is None:
                log.info("代码验证失败(幻觉?): %s", item["code"])
                continue
            log.info("代码验证通过: %s %s", info["code"], info.get("name", ""))
            codes.append(info["code"])
            matched_funds.append(
                {
                    "code": info["code"],
                    "name": info["name"] or item["name"],
                    "amount": item.get("amount"),
                }
            )

    # ── Resolve name-only funds via search ───────────────────────────────
    name_matches: list[dict] = []
    no_hit: list[dict] = []

    if name_funds:
        yield _sse(
            "step", step="search", text=f"搜索基金数据库（{len(name_funds)} 个名称）..."
        )
        if len(name_funds) > _VERIFY_LIMIT:
            truncated += [f["name"] for f in name_funds[_VERIFY_LIMIT:]]
        for fund in name_funds[:_VERIFY_LIMIT]:
            if not fund["name"]:
                continue
            try:
                results = await search_fund_by_name(fund["name"], limit=3)
            except Exception as exc:
                log.warning("名称搜索失败 '%s': %s", fund["name"], exc)
                continue
            if not results:
                log.info("名称未命中(待Pro识别): '%s'", fund["name"])
                no_hit.append(fund)
                continue
            best = results[0]
            similarity = SequenceMatcher(
                None, fund["name"], best.get("name", "")
            ).ratio()
            log.info(
                "名称匹配: OCR='%s' → 搜索='%s'(%s) 相似度=%.2f",
                fund["name"],
                best.get("name", ""),
                best["code"],
                similarity,
            )
            entry = {
                "code": best["code"],
                "name": best["name"],
                "type": best.get("type"),
                "ocr_name": fund["name"],
                "similarity": round(similarity, 2),
                "amount": fund.get("amount"),
            }
            name_matches.append(entry)
            if best["code"] not in codes:
                codes.append(best["code"])
                matched_funds.append(
                    {
                        "code": best["code"],
                        "name": best["name"],
                        "amount": fund.get("amount"),
                    }
                )

    # ── Stage 1.5: Pro identifies unmatched names ────────────────────────
    if no_hit:
        yield _sse(
            "step",
            step="pro_identify",
            text=f"Pro 模型识别未命中基金（{len(no_hit)} 个）...",
        )
        unknown_input = [{"index": i, "name": f["name"]} for i, f in enumerate(no_hit)]
        identified = await resolve_unknown_fund_names(combined_raw, unknown_input, cfg)
        for i, fund in enumerate(no_hit):
            hint = identified.get(i)
            if not hint:
                log.info("Pro未能识别: '%s'，跳过", fund["name"])
                continue
            full_name: str = hint["full_name"]
            pro_code: str | None = hint["code"]

            verified: dict | None = None
            if pro_code:
                verified = await _resolve_code(pro_code)
                if verified:
                    log.info(
                        "Pro代码核验通过: OCR='%s' → %s '%s'",
                        fund["name"],
                        pro_code,
                        verified["name"],
                    )
                else:
                    log.info("Pro代码核验失败(幻觉?): %s，回退名称搜索", pro_code)

            if not verified:
                try:
                    results = await search_fund_by_name(full_name, limit=3)
                except Exception as exc:
                    log.warning("Pro识别后名称搜索失败 '%s': %s", full_name, exc)
                    continue
                if not results:
                    log.info("Pro识别后仍未命中: '%s'", full_name)
                    continue
                best = next((r for r in results if r["code"] == pro_code), results[0])
                verified = {
                    "code": best["code"],
                    "name": best["name"],
                    "type": best.get("type"),
                }
                log.info(
                    "Pro名称搜索命中: OCR='%s' → Pro='%s' → '%s'(%s)",
                    fund["name"],
                    full_name,
                    verified["name"],
                    verified["code"],
                )

            similarity = SequenceMatcher(None, fund["name"], verified["name"]).ratio()
            entry = {
                "code": verified["code"],
                "name": verified["name"],
                "type": verified.get("type"),
                "ocr_name": fund["name"],
                "similarity": round(similarity, 2),
                "amount": fund.get("amount"),
                "review": "corrected",
                "corrected_name": full_name,
            }
            name_matches.append(entry)
            if verified["code"] not in codes:
                codes.append(verified["code"])
                matched_funds.append(
                    {
                        "code": verified["code"],
                        "name": verified["name"],
                        "amount": fund.get("amount"),
                    }
                )

    # ── Stage 2: Pro review & correction ────────────────────────────────
    preliminary = [
        {
            "index": i,
            "ocr_name": m["ocr_name"],
            "code": m["code"],
            "name": m["name"],
            "similarity": m.get("similarity", 0.0),
            "amount": m.get("amount"),
        }
        for i, m in enumerate(name_matches)
        if "review" not in m  # skip already-reviewed items from Stage 1.5
    ]

    if preliminary:
        yield _sse(
            "step",
            step="pro_review",
            text=f"Pro 模型核查匹配结果（{len(preliminary)} 个）...",
        )
        preliminary = await review_fund_matches(combined_raw, preliminary, cfg)
        for item in preliminary:
            if item.get("review") != "corrected":
                continue
            corrected = item.get("corrected_name", "")
            if not corrected:
                continue
            try:
                fix_results = await search_fund_by_name(corrected, limit=3)
            except Exception as exc:
                log.warning("纠正搜索失败 '%s': %s", corrected, exc)
                item["review"] = "unreviewed"
                continue
            if not fix_results:
                log.info("纠正搜索无结果: '%s'，保留原匹配", corrected)
                item["review"] = "unreviewed"
                continue
            best = fix_results[0]
            old_code, old_name = item["code"], item["name"]
            item["code"], item["name"] = best["code"], best["name"]
            item["type"] = best.get("type")
            item["similarity"] = SequenceMatcher(
                None, item["ocr_name"], best["name"]
            ).ratio()
            log.info(
                "Pro纠正生效: '%s'(%s) → '%s'(%s)",
                old_name,
                old_code,
                best["name"],
                best["code"],
            )
            if old_code in codes:
                codes[codes.index(old_code)] = best["code"]
            else:
                codes.append(best["code"])
            for mf in matched_funds:
                if mf["code"] == old_code:
                    mf["code"], mf["name"] = best["code"], best["name"]

        # Merge Stage 2 results back into name_matches
        reviewed = {p["index"]: p for p in preliminary}
        name_matches = [
            {
                "code": p["code"],
                "name": p["name"],
                "type": p.get("type"),
                "ocr_name": p["ocr_name"],
                "similarity": round(p.get("similarity", 0.0), 2),
                "review": p.get("review", "unreviewed"),
                "corrected_name": p.get("corrected_name"),
                "amount": p.get("amount"),
            }
            for p in reviewed.values()
        ] + [m for m in name_matches if "review" in m]  # keep Stage 1.5 items

    # ── Persist & return ─────────────────────────────────────────────────
    image_names = ",".join(fn for fn, _ in files_data)
    now = datetime.now(timezone.utc).isoformat()
    log.info("最终结果: matched_codes=%s name_matches=%d", codes, len(name_matches))
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_records(image_name,raw_text,matched_codes,created_at)"
            " VALUES(?,?,?,?)",
            (image_names, combined_raw, json.dumps(codes, ensure_ascii=False), now),
        )
        conn.commit()

    result_data: dict = {
        "ok": True,
        "image": image_names,
        "matched_codes": codes,
        "matched_funds": matched_funds,
        "name_matches": name_matches,
        "raw_text": combined_raw,
        "saved_at": now,
    }
    if truncated:
        result_data["truncated"] = truncated
        log.warning("识别结果超过上限 %d,已截断: %s", _VERIFY_LIMIT, truncated)
    yield _sse("result", data=result_data)


@router.post("/api/ocr/fund-code")
async def ocr_fund_code(
    files: list[UploadFile] = File(...),
    provider: str = Form("anthropic"),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
    model: str | None = Form(None),
    analysis_model: str | None = Form(None),
) -> StreamingResponse:
    cfg = _build_cfg(provider, api_key, base_url, model, review_model=analysis_model)
    # Read file bytes eagerly (UploadFile is not safe to use after response starts)
    files_data = [(f.filename or "upload.png", await f.read()) for f in files]
    return StreamingResponse(
        _ocr_fund_generator(files_data, cfg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/ocr/transaction")
async def ocr_transaction(
    file: UploadFile = File(...),
    provider: str = Form("anthropic"),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
    model: str | None = Form(None),
) -> dict:
    cfg = _build_cfg(provider, api_key, base_url, model)
    image_bytes = await file.read()

    path = _unique_upload_path(file.filename, "ocr_tx")
    path.write_bytes(image_bytes)

    raw_text = await run_in_threadpool(ocr_text, path)

    try:
        tx_data = await extract_transaction_from_text(raw_text, cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_ai_error(e)) from e

    return {
        "ok": True,
        "image": path.name,
        "raw_text": raw_text,
        "transaction": tx_data,
    }
