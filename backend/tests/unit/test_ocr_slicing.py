"""Unit tests for tall-screenshot slicing in ocr_service (engine mocked)."""
import cv2
import numpy as np
import pytest
from app import ocr_service
from app.ocr_service import _merge_overlap


class TestMergeOverlap:
    def test_drops_repeated_overlap_prefix(self):
        acc = ["a", "b", "c", "d"]
        new = ["c", "d", "e", "f"]
        assert _merge_overlap(acc, new) == ["a", "b", "c", "d", "e", "f"]

    def test_no_overlap_appends_all(self):
        assert _merge_overlap(["a", "b"], ["c", "d"]) == ["a", "b", "c", "d"]

    def test_empty_sides(self):
        assert _merge_overlap([], ["a"]) == ["a"]
        assert _merge_overlap(["a"], []) == ["a"]


@pytest.fixture
def fake_engine(monkeypatch):
    """Replace _ocr_image with a stub that records each chunk's shape."""
    calls: list[tuple] = []

    def _stub(img):
        calls.append(img.shape if hasattr(img, "shape") else img)
        return [f"chunk{len(calls)}"]

    monkeypatch.setattr(ocr_service, "_ocr_image", _stub)
    return calls


def _write_image(tmp_path, h, w):
    path = tmp_path / f"img_{h}x{w}.png"
    cv2.imwrite(str(path), np.full((h, w, 3), 255, dtype=np.uint8))
    return path


class TestRunOcrLines:
    def test_tall_screenshot_is_sliced_with_overlap(self, tmp_path, fake_engine):
        path = _write_image(tmp_path, 4000, 1000)

        lines = ocr_service._run_ocr_lines(path)

        # step = 1600 - 200 = 1400 -> chunks at y=0/1400/2800 (last 1200 tall)
        assert len(fake_engine) == 3
        assert all(shape[1] == 1000 for shape in fake_engine)
        assert lines == ["chunk1", "chunk2", "chunk3"]

    def test_normal_screenshot_single_pass(self, tmp_path, fake_engine):
        path = _write_image(tmp_path, 1920, 1080)  # h < 2*w

        lines = ocr_service._run_ocr_lines(path)

        assert len(fake_engine) == 1
        assert lines == ["chunk1"]

    def test_unreadable_file_falls_back_to_engine_loader(self, tmp_path, fake_engine):
        path = tmp_path / "broken.png"
        path.write_bytes(b"not an image")

        lines = ocr_service._run_ocr_lines(path)

        # cv2.imread fails -> path string handed to the engine loader
        assert fake_engine == [str(path)]
        assert lines == ["chunk1"]
