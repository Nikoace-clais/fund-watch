"""Test fund repository."""
import pytest
from fund_watch.repositories.fund_repo import FundRepository, init_db, get_conn


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Create repository with temp database."""
    import fund_watch.repositories.fund_repo as repo_module
    # Patch DB_PATH to use temp location
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(repo_module, "DB_PATH", test_db)
    init_db()
    return FundRepository()


@pytest.mark.unit
def test_init_db_creates_tables(repo):
    """Test database initialization creates tables."""
    with get_conn() as conn:
        # Check funds table exists
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='funds'"
        ).fetchone()
        assert row is not None


@pytest.mark.unit
def test_create_fund(repo):
    """Test creating a fund."""
    fund = repo.create("110011", "Test Fund")
    
    assert fund["code"] == "110011"
    assert fund["name"] == "Test Fund"
    assert "created_at" in fund


@pytest.mark.unit
def test_get_by_code(repo):
    """Test getting fund by code."""
    repo.create("110011", "Test Fund")
    
    fund = repo.get_by_code("110011")
    assert fund is not None
    assert fund["code"] == "110011"
    
    # Non-existent fund
    assert repo.get_by_code("999999") is None


@pytest.mark.unit
def test_get_all(repo):
    """Test getting all funds."""
    repo.create("110011", "Fund 1")
    repo.create("110022", "Fund 2")
    
    funds = repo.get_all()
    assert len(funds) == 2
    codes = [f["code"] for f in funds]
    assert "110011" in codes
    assert "110022" in codes


@pytest.mark.unit
def test_delete_fund(repo):
    """Test deleting fund."""
    repo.create("110011", "Test Fund")
    
    assert repo.delete("110011") is True
    assert repo.get_by_code("110011") is None
    assert repo.delete("110011") is False  # Already deleted


@pytest.mark.unit
def test_batch_create(repo):
    """Test batch creating funds."""
    result = repo.batch_create(["110011", "110022", "110033"])
    
    assert result["inserted"] == 3
    assert result["total"] == 3
    
    # Duplicate codes should be skipped
    result = repo.batch_create(["110011", "110044"])
    assert result["inserted"] == 1
    assert result["total"] == 2
