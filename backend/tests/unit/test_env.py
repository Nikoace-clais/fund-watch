"""Test environment setup."""


def test_uv_environment():
    """Verify we're running in a virtual environment (uv-managed)."""
    import sys

    assert sys.prefix != sys.base_prefix


def test_imports_work():
    """Verify all dependencies can be imported."""
    import fastapi
    import httpx
    import uvicorn

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
