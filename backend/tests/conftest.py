from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app import db, main

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_fund_watch.db")
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    db.init_db()

    return TestClient(main.app)
