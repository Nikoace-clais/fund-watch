from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

CODE_RE = re.compile(r"\b\d{6}\b")
# Match amounts like: ¥1,234.56  1,234.56元  1234.56  持有金额 1,234.56
AMOUNT_RE = re.compile(r"[¥￥]?\s*([\d,]+\.\d{1,2})\s*元?")


def extract_fund_codes_from_image(image_path: Path) -> tuple[str, list[str]]:
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", []

    raw_text = "\n".join([line[1] for line in result if len(line) >= 2])
    codes = sorted(set(CODE_RE.findall(raw_text)))
    return raw_text, codes


def extract_funds_with_amounts(image_path: Path) -> tuple[str, list[dict]]:
    """Extract fund codes and nearby amounts from OCR text.

    Returns (raw_text, matched_funds) where matched_funds is a list of
    {"code": "161725", "amount": 1234.56} dicts. amount may be None.
    """
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", []

    # result items: [bbox, text, confidence]
    lines = [line[1] for line in result if len(line) >= 2]
    raw_text = "\n".join(lines)

    matched_funds: list[dict] = []
    seen_codes: set[str] = set()

    for i, line_text in enumerate(lines):
        codes_in_line = CODE_RE.findall(line_text)
        for code in codes_in_line:
            if code in seen_codes:
                continue
            seen_codes.add(code)

            # Search current line and nearby lines (±2) for an amount
            amount = _find_nearby_amount(lines, i, window=2)
            matched_funds.append({"code": code, "amount": amount})

    return raw_text, matched_funds


def _find_nearby_amount(lines: list[str], center: int, window: int = 2) -> float | None:
    """Search lines around center index for an amount pattern."""
    start = max(0, center - window)
    end = min(len(lines), center + window + 1)

    for idx in range(start, end):
        m = AMOUNT_RE.search(lines[idx])
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None
