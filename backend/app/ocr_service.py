from __future__ import annotations

import re
import threading
from pathlib import Path

import cv2
from rapidocr_onnxruntime import RapidOCR

_ocr_engine: RapidOCR | None = None
# Engine init and inference are not thread-safe; routes call us via threadpool
_ocr_lock = threading.Lock()

# Tall scroll-screenshots are sliced into overlapping chunks: the engine's
# global max_side_len would otherwise downscale them until small text
# (fund codes, amounts) becomes illegible.
_SLICE_HEIGHT = 1600
_SLICE_OVERLAP = 200  # must exceed one text-line height so no line is cut
_MIN_TAIL = 80  # skip leftover slivers shorter than a text line


def _get_ocr() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        # Recall-biased: regex extraction + code verification downstream filter
        # the extra noise, so a lower text_score is a net win; max_side_len
        # raised so medium-long screenshots are not downscaled as hard.
        _ocr_engine = RapidOCR(text_score=0.4, max_side_len=3500)
    return _ocr_engine


def _ocr_image(img) -> list[str]:
    """Run the engine on one image (ndarray or path str), return text lines."""
    result, _ = _get_ocr()(img)
    if not result:
        return []
    return [line[1] for line in result if len(line) >= 2]


def _merge_overlap(acc: list[str], new: list[str], max_lines: int = 12) -> list[str]:
    """Append new lines, dropping the prefix already seen in the chunk overlap."""
    k = min(len(acc), len(new), max_lines)
    while k > 0 and acc[-k:] != new[:k]:
        k -= 1
    return acc + new[k:]


def _run_ocr_lines(image_path: Path) -> list[str]:
    """Run OCR and return recognized text lines (tall images sliced)."""
    img = cv2.imread(str(image_path))
    if img is None:
        # Format cv2 can't decode — let the engine's own loader try
        with _ocr_lock:
            return _ocr_image(str(image_path))

    h, w = img.shape[:2]
    with _ocr_lock:
        if h <= 2 * w or h <= _SLICE_HEIGHT:
            return _ocr_image(img)
        lines: list[str] = []
        step = _SLICE_HEIGHT - _SLICE_OVERLAP
        for top in range(0, h, step):
            chunk = img[top : top + _SLICE_HEIGHT]
            if chunk.shape[0] < _MIN_TAIL:
                break
            lines = _merge_overlap(lines, _ocr_image(chunk))
        return lines


CODE_RE = re.compile(r"\b\d{6}\b")
# Match amounts like: ¥1,234.56  1,234.56元  1234.56  持有金额 1,234.56
AMOUNT_RE = re.compile(r"[¥￥]?\s*([\d,]+\.\d{1,2})\s*元?")

# Common fund name patterns — match Chinese fund names in OCR text
# e.g. "易方达优质精选混合(QDII)", "招商中证白酒指数A", "广发科技先锋混合"
FUND_NAME_RE = re.compile(
    r"([\u4e00-\u9fff]{2,}(?:[\u4e00-\u9fff]+)+"  # 2+ groups of Chinese chars
    r"(?:\([A-Za-z]+\)|[A-Za-z])?)"  # optional (QDII) or trailing A/C
)

# Transaction OCR patterns
BUY_RE = re.compile(r"买入|申购|定投|认购", re.IGNORECASE)
SELL_RE = re.compile(r"卖出|赎回|转出", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
NAV_RE = re.compile(r"净值[：:]*\s*([\d.]+)|单位净值[：:]*\s*([\d.]+)|([\d]\.\d{4})")
SHARES_RE = re.compile(
    r"份额[：:]*\s*([\d,.]+)|确认份额[：:]*\s*([\d,.]+)|([\d,]+\.\d{2,4})\s*份"
)


def extract_fund_codes_from_image(image_path: Path) -> tuple[str, list[str]]:
    lines = _run_ocr_lines(image_path)
    raw_text = "\n".join(lines)
    codes = sorted(set(CODE_RE.findall(raw_text)))
    return raw_text, codes


def extract_funds_with_amounts(image_path: Path) -> tuple[str, list[dict]]:
    """Extract fund codes and nearby amounts from OCR text.

    Returns (raw_text, matched_funds) where matched_funds is a list of
    {"code": "161725", "amount": 1234.56} dicts. amount may be None.
    """
    lines = _run_ocr_lines(image_path)
    return "\n".join(lines), _match_funds_with_amounts(lines)


def scan_fund_image(image_path: Path) -> tuple[str, list[str], list[dict]]:
    """Single OCR pass returning (raw_text, codes, funds_with_amounts)."""
    lines = _run_ocr_lines(image_path)
    raw_text = "\n".join(lines)
    codes = sorted(set(CODE_RE.findall(raw_text)))
    return raw_text, codes, _match_funds_with_amounts(lines)


def _match_funds_with_amounts(lines: list[str]) -> list[dict]:
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

    return matched_funds


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


def extract_fund_names_from_text(raw_text: str) -> list[str]:
    """Extract potential fund names from OCR text.

    Looks for patterns like "XX基金", "XX混合", "XX指数", "XX债券" etc.
    Returns deduplicated list of candidate fund name strings.
    """
    # Keywords that indicate a fund name
    fund_keywords = (
        "混合",
        "指数",
        "债券",
        "货币",
        "股票",
        "增长",
        "价值",
        "优选",
        "精选",
        "成长",
        "稳健",
        "增强",
        "量化",
        "ETF",
        "LOF",
        "FOF",
        "QDII",
        "联接",
        "定开",
        "定期",
        "灵活",
        "配置",
        "收益",
        "回报",
        "先锋",
        "科技",
        "医疗",
        "消费",
        "新能源",
        "半导体",
        "白酒",
        "红利",
        "养老",
        "平衡",
        "主题",
        "行业",
        "策略",
    )

    candidates: list[str] = []
    seen: set[str] = set()

    for line in raw_text.split("\n"):
        # Skip very short or very long lines
        if len(line) < 4 or len(line) > 50:
            continue
        # Check if line contains fund-related keywords
        has_keyword = any(kw in line for kw in fund_keywords)
        if not has_keyword:
            continue
        # Take the whole line as the name candidate, then clean it up
        # Clean up common prefixes/suffixes
        name = line.strip()
        # Remove leading numbers, dots, punctuation
        name = re.sub(r"^[\d.\s、]+", "", name)
        # Remove trailing amounts
        name = re.sub(r"[\d,]+\.\d{2}.*$", "", name)
        name = name.strip()
        if len(name) < 4 or name in seen:
            continue
        # Must contain at least 2 Chinese characters
        if len(re.findall(r"[\u4e00-\u9fff]", name)) < 2:
            continue
        seen.add(name)
        candidates.append(name)

    return candidates


def extract_transaction_from_image(image_path: Path) -> tuple[str, dict]:
    """Extract transaction details from a screenshot.

    Returns (raw_text, tx_data) where tx_data has keys:
    direction, code, trade_date, nav, shares, amount — all may be None.
    """
    lines = _run_ocr_lines(image_path)
    if not lines:
        return "", {}

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
