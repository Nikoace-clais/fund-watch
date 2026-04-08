"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create app instance for testing."""
    from fund_watch.main import app
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_fund_data():
    """Sample fund data for testing."""
    return {
        "code": "110011",
        "name": "易方达中小盘混合",
        "category": "混合型",
    }
