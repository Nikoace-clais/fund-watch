"""Test environment setup."""
import pytest


def test_uv_environment():
    """Verify we're running in uv environment."""
    import sys
    # Check that we're using the venv Python
    assert ".venv" in sys.executable or "virtualenvs" in sys.executable


def test_imports_work():
    """Verify all dependencies can be imported."""
    import fastapi
    import uvicorn
    import httpx
    import pydantic
    import pytest_asyncio
    
    assert fastapi.__version__
    assert uvicorn.__version__
    assert httpx.__version__


def test_project_structure_exists():
    """Verify new project structure is in place."""
    from pathlib import Path
    backend = Path(__file__).parent.parent.parent
    
    # Check key directories exist
    assert (backend / "app").exists()
    assert (backend / "tests" / "unit").exists()
    assert (backend / "tests" / "integration").exists()
