"""Test fund import service."""
import pytest
from unittest.mock import Mock, patch

from fund_watch.services.import_service import FundImportService, ImportResult


@pytest.fixture
def import_service(tmp_path, monkeypatch):
    """Create import service with temp database."""
    import fund_watch.repositories.fund_repo as repo_module
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(repo_module, "DB_PATH", test_db)
    from fund_watch.repositories.fund_repo import init_db
    init_db()
    return FundImportService()


@pytest.mark.unit
def test_extract_fund_codes_from_text(import_service):
    """Test extracting 6-digit fund codes from text."""
    text = "我的基金持仓：易方达蓝筹005827，招商白酒161725"
    codes = import_service._extract_fund_codes(text)
    
    assert "005827" in codes
    assert "161725" in codes
    assert len(codes) == 2


@pytest.mark.unit
def test_extract_fund_codes_no_duplicates(import_service):
    """Test no duplicate codes extracted."""
    text = "005827 005827 005827"
    codes = import_service._extract_fund_codes(text)
    
    assert len(codes) == 1
    assert codes[0] == "005827"


@pytest.mark.unit
def test_fuzzy_match_fund_name(import_service):
    """Test fuzzy matching fund names."""
    # Mock the database
    mock_funds = [
        {"code": "005827", "name": "易方达蓝筹精选混合", "type": "混合型"},
        {"code": "110011", "name": "易方达中小盘混合", "type": "混合型"},
    ]
    
    with patch.object(import_service.repo, 'get_all', return_value=mock_funds):
        matches = import_service._fuzzy_match_name("易方达蓝筹")
        
        assert len(matches) > 0
        assert any(m["code"] == "005827" for m in matches)


@pytest.mark.unit
def test_calculate_confidence_high(import_service):
    """Test high confidence calculation."""
    # Exact code match should have high confidence
    confidence = import_service._calculate_confidence(
        code="005827",
        matched_name="易方达蓝筹精选混合",
        source="code",
        raw_text="易方达蓝筹005827"
    )
    
    assert confidence >= 0.9


@pytest.mark.unit
def test_calculate_confidence_low(import_service):
    """Test low confidence for name-only match."""
    confidence = import_service._calculate_confidence(
        code="005827",
        matched_name="易方达蓝筹精选混合",
        source="name_match",
        raw_text="蓝筹基金"  # Vague text
    )
    
    assert confidence < 0.8


@pytest.mark.unit
def test_preview_result_structure(import_service):
    """Test preview result has required fields."""
    # Mock OCR result
    with patch.object(import_service, '_ocr_image', return_value="005827 易方达蓝筹"):
        with patch.object(import_service, '_validate_fund', return_value={
            "code": "005827",
            "name": "易方达蓝筹精选混合",
            "type": "混合型"
        }):
            result = import_service.preview_import(b"fake_image_data")
    
    assert isinstance(result, ImportResult)
    assert hasattr(result, 'funds')
    assert hasattr(result, 'total_confidence')
    assert hasattr(result, 'needs_review')
    assert hasattr(result, 'total_count')
    
    if result.funds:
        fund = result.funds[0]
        assert hasattr(fund, 'code')
        assert hasattr(fund, 'name')
        assert hasattr(fund, 'type')
        assert hasattr(fund, 'confidence')
        assert hasattr(fund, 'source')
        assert hasattr(fund, 'needs_review')


@pytest.mark.unit
def test_needs_review_threshold(import_service):
    """Test needs_review flag based on confidence threshold."""
    # High confidence - no review needed
    assert not import_service._should_need_review(0.85)
    
    # Low confidence - needs review
    assert import_service._should_need_review(0.65)
    
    # Borderline (exactly at threshold) - needs review
    assert import_service._should_need_review(0.74)


@pytest.mark.unit
def test_confirm_import(import_service):
    """Test confirming import adds funds."""
    codes = ["005827", "110011"]
    
    with patch.object(import_service.repo, 'batch_create') as mock_batch:
        mock_batch.return_value = {"inserted": 2, "total": 2}
        result = import_service.confirm_import(codes)
    
    assert result["success"] is True
    assert result["added"] == 2


@pytest.mark.unit  
def test_confirm_import_empty_list(import_service):
    """Test confirming import with empty list."""
    result = import_service.confirm_import([])
    
    assert result["success"] is True
    assert result["added"] == 0


@pytest.mark.unit
def test_extract_from_table_structure(import_service):
    """Test extracting funds from table-like text."""
    # Table-like text with columns
    text = """
    基金名称        基金代码    持仓金额
    易方达蓝筹      005827      10000
    招商白酒        161725      5000
    """
    
    codes = import_service._extract_from_table(text)
    
    assert "005827" in codes
    assert "161725" in codes
