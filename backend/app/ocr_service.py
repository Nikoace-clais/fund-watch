from __future__ import annotations

import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

CODE_RE = re.compile(r"\b\d{6}\b")


def extract_fund_codes_from_image(image_path: Path) -> tuple[str, list[str]]:
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    if not result:
        return "", []

    raw_text = "\n".join([line[1] for line in result if len(line) >= 2])
    codes = sorted(set(CODE_RE.findall(raw_text)))
    return raw_text, codes
