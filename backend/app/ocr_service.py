from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

CODE_RE = re.compile(r"\b\d{6}\b")
# Match amounts like: ¥1,234.56  1,234.56元  1234.56  持有金额 1,234.56
AMOUNT_RE = re.compile(r"[¥￥]?\s*([\d,]+\.\d{1,2})\s*元?")

# Transaction OCR patterns
BUY_RE = re.compile(r"买入|申购|定投|认购", re.IGNORECASE)
SELL_RE = re.compile(r"卖出|赎回|转出", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
NAV_RE = re.compile(r"净值[：:]*\s*([\d.]+)|单位净值[：:]*\s*([\d.]+)|([\d]\.\d{4})")
SHARES_RE = re.compile(r"份额[：:]*\s*([\d,.]+)|确认份额[：:]*\s*([\d,.]+)|([\d,]+\.\d{2,4})\s*份")


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


def extract_transaction_from_image(image_path: Path) -> tuple[str, dict]:
    """Extract transaction details from a screenshot.

    Returns (raw_text, tx_data) where tx_data has keys:
    direction, code, trade_date, nav, shares, amount — all may be None.
    """
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", {}

    lines = [line[1] for line in result if len(line) >= 2]
    raw_text = "\n".join(lines)
    full_text = " ".join(lines)

    tx: dict = {
        "direction": None,
        "code": None,
        "trade_date": None,
        "nav": None,
        "shares": None,
        "amount": None,
    }

    # Direction
    if BUY_RE.search(full_text):
        tx["direction"] = "buy"
    elif SELL_RE.search(full_text):
        tx["direction"] = "sell"

    # Fund code
    codes = CODE_RE.findall(full_text)
    if codes:
        tx["code"] = codes[0]

    # Date
    dm = DATE_RE.search(full_text)
    if dm:
        tx["trade_date"] = dm.group(1).replace("/", "-")

    # NAV — search each line
    for line in lines:
        nm = NAV_RE.search(line)
        if nm:
            tx["nav"] = next(g for g in nm.groups() if g)
            break

    # Shares
    for line in lines:
        sm = SHARES_RE.search(line)
        if sm:
            tx["shares"] = next(g for g in sm.groups() if g).replace(",", "")
            break

    # Amount
    for line in lines:
        if any(kw in line for kw in ("金额", "扣款", "确认金额", "交易金额")):
            am = AMOUNT_RE.search(line)
            if am:
                tx["amount"] = am.group(1).replace(",", "")
                break

    return raw_text, tx
