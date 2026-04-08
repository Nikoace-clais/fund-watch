"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient

from fund_watch.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.integration
def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration  
def test_list_funds(client):
    """Test list funds endpoint."""
    response = client.get("/api/funds")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.integration
def test_add_fund_invalid_code(client):
    """Test adding fund with invalid code."""
    response = client.post("/api/funds/invalid")
    assert response.status_code == 400


@pytest.mark.integration
def test_delete_nonexistent_fund(client):
    """Test deleting non-existent fund."""
    response = client.delete("/api/funds/999999")
    assert response.status_code == 404
