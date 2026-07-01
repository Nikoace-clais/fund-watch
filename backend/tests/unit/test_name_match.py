"""Unit tests for fund-name normalization and share-class ranking helpers."""

import sys
from pathlib import Path

# Allow importing from app package without installing
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.routers.ocr import _normalize_query, _pick_best, _share_class


def test_normalize_qdii_etf():
    assert _normalize_query("广发纳斯达克100ETF联接(QDII)A") == "广发纳斯达克100"


def test_normalize_flexible_alloc():
    assert _normalize_query("万家品质生活灵活配置混合A") == "万家品质生活"


def test_normalize_long_etf_link():
    assert _normalize_query("华泰柏瑞中证红利低波动ETF联接C") == "华泰柏瑞中证红利低波动"


def test_normalize_short_name_untouched():
    # brand+theme only, nothing to strip — result should not be empty
    r = _normalize_query("博时黄金ETF联接C")
    assert r == "博时黄金"


def test_share_class_a():
    assert _share_class("万家品质生活混合A") == "A"


def test_share_class_c_qdii():
    assert _share_class("摩根标普500指数(QDII)C") == "C"


def test_share_class_empty():
    assert _share_class("博时黄金ETF") == ""


def test_pick_best_prefers_matching_share_class():
    c_cand = {"code": "016600", "name": "万家品质生活混合C"}
    a_cand = {"code": "519195", "name": "万家品质生活混合A"}
    picked = _pick_best("万家品质生活灵活配置混合A", [c_cand, a_cand])
    assert picked is not None
    assert picked["code"] == "519195"


def test_pick_best_empty_candidates():
    assert _pick_best("随便", []) is None
