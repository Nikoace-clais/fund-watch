"""Fund import service with OCR and fuzzy matching."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

from ..repositories.fund_repo import FundRepository

logger = logging.getLogger('fund-watch.import')


@dataclass
class ImportPreviewItem:
    """Single fund import preview item."""
    code: str
    name: str
    type: str
    confidence: float
    source: str  # 'code', 'name_match', 'table'
    needs_review: bool


@dataclass
class ImportResult:
    """Import preview result."""
    funds: list[ImportPreviewItem]
    total_confidence: float
    needs_review: bool
    total_count: int


class FundImportService:
    """Service for importing funds from images with OCR and fuzzy matching."""
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    LOW_CONFIDENCE = 0.75
    
    def __init__(self, repo: FundRepository | None = None):
        self.repo = repo or FundRepository()
        self._fund_cache: list[dict] | None = None
    
    def _get_all_funds(self) -> list[dict]:
        """Get all funds from database (with caching)."""
        if self._fund_cache is None:
            self._fund_cache = self.repo.get_all()
        return self._fund_cache
    
    def _ocr_image(self, image_data: bytes) -> str:
        """OCR image to extract text.
        
        Note: Currently uses paddleocr if available, falls back to mock for testing.
        """
        logger.info(f"📸 Starting OCR on {len(image_data)} bytes image")
        start_time = time.time()
        
        try:
            from paddleocr import PaddleOCR
            
            # Initialize OCR (lazy loading)
            if not hasattr(self, '_ocr'):
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='ch',
                    show_log=False
                )
            
            # Save image temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_path = f.name
            
            # Run OCR
            result = self._ocr.ocr(temp_path, cls=True)
            
            # Cleanup
            import os
            os.unlink(temp_path)
            
            # Extract text
            texts = []
            if result and result[0]:
                for line in result[0]:
                    if line:
                        texts.append(line[1][0])  # text content
            
            elapsed = time.time() - start_time
            logger.info(f"✅ OCR completed in {elapsed:.2f}s, extracted {len(texts)} lines")
            
            return '\n'.join(texts)
        except Exception as e:
            # Fallback: return empty string for testing
            logger.warning(f"⚠️ OCR failed: {e}, using fallback")
            return ""
    
    def _extract_fund_codes(self, text: str) -> list[str]:
        """Extract 6-digit fund codes from text."""
        # Match 6 consecutive digits (fund codes are typically 6 digits)
        # Use word boundary or look for digits surrounded by non-digits
        pattern = r'(?:^|\D)(\d{6})(?:\D|$)'
        matches = re.findall(pattern, text)
        
        # Remove duplicates while preserving order
        seen = set()
        codes = []
        for code in matches:
            if code not in seen:
                seen.add(code)
                codes.append(code)
        
        return codes
    
    def _extract_from_table(self, text: str) -> list[str]:
        """Extract fund codes from table-like structures."""
        codes = []
        lines = text.strip().split('\n')
        
        for line in lines:
            # Look for patterns like: name code amount
            # Example: "易方达蓝筹 005827 10000"
            match = re.search(r'[\u4e00-\u9fa5]+.*?\b(\d{6})\b', line)
            if match:
                code = match.group(1)
                if code not in codes:
                    codes.append(code)
        
        return codes
    
    def _fuzzy_match_name(self, text: str) -> list[dict]:
        """Fuzzy match fund names from text."""
        all_funds = self._get_all_funds()
        if not all_funds:
            return []
        
        matches = []
        
        # Extract potential fund names (Chinese characters sequences)
        # This is a simple heuristic - fund names typically have 4-15 Chinese chars
        potential_names = re.findall(r'[\u4e00-\u9fa5]{4,15}', text)
        
        for name in potential_names:
            # Use rapidfuzz to find best matches
            fund_names = [f["name"] for f in all_funds]
            results = process.extract(name, fund_names, scorer=fuzz.partial_ratio, limit=3)
            
            for matched_name, score, _ in results:
                if score >= 70:  # Threshold for fuzzy match
                    # Find the fund with this name
                    for fund in all_funds:
                        if fund["name"] == matched_name:
                            matches.append({
                                **fund,
                                "match_score": score / 100.0,
                                "matched_text": name
                            })
                            break
        
        return matches
    
    def _validate_fund(self, code: str) -> dict | None:
        """Validate fund exists and get info."""
        # First check local database
        fund = self.repo.get_by_code(code)
        if fund:
            return fund
        
        # If not in DB, try to fetch from external source
        try:
            from ..external import fetch_fund_info
            import asyncio
            
            info = asyncio.run(fetch_fund_info(code))
            if info.get("name"):
                return {
                    "code": code,
                    "name": info["name"],
                    "type": info.get("type", "未知"),
                }
        except Exception:
            pass
        
        return None
    
    def _calculate_confidence(
        self,
        code: str,
        matched_name: str,
        source: str,
        raw_text: str
    ) -> float:
        """Calculate confidence score for a match."""
        if source == "code":
            # Direct code match - high confidence
            base_confidence = 0.95
            
            # Bonus if name also appears nearby
            if matched_name and matched_name in raw_text:
                base_confidence = 0.98
            
            return base_confidence
        
        elif source == "name_match":
            # Name fuzzy match - medium confidence based on fuzz score
            # This would be passed in from _fuzzy_match_name
            return 0.75
        
        elif source == "table":
            # Table extraction - medium-high confidence
            return 0.85
        
        return 0.5
    
    def _should_need_review(self, confidence: float) -> bool:
        """Determine if a match needs manual review."""
        return confidence < self.LOW_CONFIDENCE
    
    def preview_import(self, image_data: bytes) -> ImportResult:
        """Generate import preview from image."""
        logger.info("🔍 Starting import preview generation")
        start_time = time.time()
        
        # Step 1: OCR
        raw_text = self._ocr_image(image_data)
        
        if not raw_text:
            logger.warning("⚠️ No text extracted from image")
            return ImportResult(
                funds=[],
                total_confidence=0.0,
                needs_review=True,
                total_count=0
            )
        
        # Step 2: Multi-strategy extraction
        found_codes: dict[str, dict] = {}  # code -> {source, confidence}
        
        # Strategy 1: Direct code extraction
        code_matches = self._extract_fund_codes(raw_text)
        for code in code_matches:
            if code not in found_codes:
                found_codes[code] = {"source": "code"}
        logger.debug(f"📋 Code extraction: {len(code_matches)} codes found")
        
        # Strategy 2: Table extraction
        table_matches = self._extract_from_table(raw_text)
        for code in table_matches:
            if code not in found_codes:
                found_codes[code] = {"source": "table"}
        logger.debug(f"📊 Table extraction: {len(table_matches)} codes found")
        
        # Strategy 3: Name fuzzy match
        name_matches = self._fuzzy_match_name(raw_text)
        for match in name_matches:
            code = match["code"]
            if code not in found_codes:
                found_codes[code] = {
                    "source": "name_match",
                    "match_score": match.get("match_score", 0.7)
                }
        logger.debug(f"🔤 Name matching: {len(name_matches)} funds found")
        
        # Step 3: Validate and build preview
        funds = []
        total_confidence = 0.0
        needs_review = False
        
        for code, info in found_codes.items():
            fund_data = self._validate_fund(code)
            if not fund_data:
                logger.debug(f"⚠️ Fund {code} validation failed")
                continue
            
            # Calculate confidence
            if info["source"] == "name_match" and "match_score" in info:
                confidence = info["match_score"]
            else:
                confidence = self._calculate_confidence(
                    code=code,
                    matched_name=fund_data.get("name", ""),
                    source=info["source"],
                    raw_text=raw_text
                )
            
            item_needs_review = self._should_need_review(confidence)
            needs_review = needs_review or item_needs_review
            total_confidence += confidence
            
            funds.append(ImportPreviewItem(
                code=code,
                name=fund_data.get("name", ""),
                type=fund_data.get("type", "未知"),
                confidence=confidence,
                source=info["source"],
                needs_review=item_needs_review
            ))
        
        # Sort by confidence (highest first)
        funds.sort(key=lambda x: x.confidence, reverse=True)
        
        # Calculate average confidence
        avg_confidence = total_confidence / len(funds) if funds else 0.0
        
        elapsed = time.time() - start_time
        high_conf = sum(1 for f in funds if f.confidence >= 0.85)
        review_count = sum(1 for f in funds if f.needs_review)
        
        logger.info(
            f"✅ Preview generated in {elapsed:.2f}s | "
            f"Total: {len(funds)} | "
            f"High conf: {high_conf} | "
            f"Need review: {review_count} | "
            f"Avg conf: {avg_confidence:.0%}"
        )
        
        return ImportResult(
            funds=funds,
            total_confidence=round(avg_confidence, 2),
            needs_review=needs_review,
            total_count=len(funds)
        )
    
    def confirm_import(self, codes: list[str]) -> dict:
        """Confirm import of selected funds."""
        logger.info(f"💾 Confirming import of {len(codes)} funds")
        
        if not codes:
            logger.debug("No codes provided, returning empty result")
            return {
                "success": True,
                "added": 0,
                "total": 0,
                "invalid": []
            }
        
        # Validate all codes first
        valid_codes = []
        invalid = []
        
        for code in codes:
            fund = self._validate_fund(code)
            if fund:
                valid_codes.append(code)
            else:
                invalid.append(code)
                logger.warning(f"⚠️ Invalid fund code: {code}")
        
        # Batch create
        result = self.repo.batch_create(valid_codes)
        
        logger.info(
            f"✅ Import complete: {result['inserted']} added, "
            f"{len(invalid)} invalid"
        )
        
        return {
            "success": True,
            "added": result["inserted"],
            "total": len(codes),
            "invalid": invalid
        }
