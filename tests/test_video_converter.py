"""Tests for the VideoConverter."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from fileconverter.converters.video import VideoConverter


@pytest.fixture
def converter():
    return VideoConverter()


@pytest.fixture
def converter_extract():
    return VideoConverter(extract_images=True)


@pytest.fixture
def converter_custom_interval():
    return VideoConverter(frame_interval=10.0)


def _make_mock_capture(fps=30.0, width=640, height=480, num_frames=150, is_opened=True):
    """Create a mock cv2.VideoCapture that yields synthetic frames."""
    import cv2

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = is_opened

    prop_map = {
        cv2.CAP_PROP_FPS: fps,
        cv2.CAP_PROP_FRAME_COUNT: num_frames,
        cv2.CAP_PROP_FRAME_WIDTH: width,
        cv2.CAP_PROP_FRAME_HEIGHT: height,
    }

    def mock_get(prop):
        return prop_map.get(int(prop), 0)

    mock_cap.get.side_effect = mock_get

    frame = np.full((height, width, 3), 255, dtype=np.uint8)
    call_count = [0]

    def mock_read():
        if call_count[0] < num_frames:
            call_count[0] += 1
            return True, frame.copy()
        return False, None

    mock_cap.read.side_effect = mock_read
    return mock_cap


class TestSupportedExtensions:
    def test_returns_all_video_extensions(self):
        exts = VideoConverter.supported_extensions()
        assert exts == [".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv"]

    def test_returns_list(self):
        assert isinstance(VideoConverter.supported_extensions(), list)


class TestConvertSuccess:
    def test_successful_conversion_with_text(self, converter, tmp_path):
        video_file = tmp_path / "lecture.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="Hello World"):
            result = converter.convert(video_file)

        assert result.success is True
        assert "# Video: lecture.mp4" in result.markdown
        assert "**Duration:**" in result.markdown
        assert "**Resolution:** 640x480" in result.markdown
        assert "## Extracted Text by Timestamp" in result.markdown
        assert "Hello World" in result.markdown

    def test_successful_conversion_no_text(self, converter, tmp_path):
        video_file = tmp_path / "silent.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="   "):
            result = converter.convert(video_file)

        assert result.success is True
        assert "*No text detected in any extracted frame.*" in result.markdown

    def test_metadata_line_present(self, converter, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=24.0, num_frames=240, width=1920, height=1080)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value=""):
            result = converter.convert(video_file)

        assert "**Resolution:** 1920x1080" in result.markdown
        assert "**FPS:** 24.0" in result.markdown

    def test_no_frames_extracted(self, converter, tmp_path):
        video_file = tmp_path / "empty.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=0)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = converter.convert(video_file)

        assert result.success is True
        assert "*No frames could be extracted from this video.*" in result.markdown


class TestDeduplication:
    def test_duplicate_frames_are_collapsed(self, converter, tmp_path):
        video_file = tmp_path / "slides.mp4"
        video_file.touch()

        # 15 seconds at 30fps -> frames at 0s, 5s, 10s; all same text
        mock_cap = _make_mock_capture(fps=30.0, num_frames=450)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="Same slide"):
            result = converter.convert(video_file)

        assert result.success is True
        assert result.markdown.count("Same slide") == 1

    def test_different_text_not_deduplicated(self, converter, tmp_path):
        video_file = tmp_path / "changing.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=300)
        call_count = [0]
        texts = ["Slide 1", "Slide 2"]

        def varying_ocr(img, **kwargs):
            idx = min(call_count[0], len(texts) - 1)
            call_count[0] += 1
            return texts[idx]

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", side_effect=varying_ocr):
            result = converter.convert(video_file)

        assert "Slide 1" in result.markdown
        assert "Slide 2" in result.markdown


class TestExtractImages:
    def test_extract_images_saves_frames(self, converter_extract, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="text"):
            result = converter_extract.convert(video_file)

        assert result.success is True
        assert len(result.images_extracted) >= 1
        frames_dir = tmp_path / "test_frames"
        assert frames_dir.exists()

    def test_extract_images_embeds_references(self, converter_extract, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="text"):
            result = converter_extract.convert(video_file)

        assert "![Frame at" in result.markdown

    def test_images_not_extracted_by_default(self, converter, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="text"):
            result = converter.convert(video_file)

        assert result.images_extracted == []
        assert "![" not in result.markdown


class TestErrorHandling:
    def test_opencv_not_installed(self, converter, tmp_path):
        fake_path = tmp_path / "video.mp4"
        fake_path.touch()

        with patch("builtins.__import__", side_effect=_import_blocker("cv2")):
            result = converter.convert(fake_path)

        assert result.success is False
        assert "opencv-python is not installed" in result.error

    def test_pytesseract_not_installed(self, converter, tmp_path):
        fake_path = tmp_path / "video.mp4"
        fake_path.touch()

        with patch("builtins.__import__", side_effect=_import_blocker("pytesseract")):
            result = converter.convert(fake_path)

        assert result.success is False
        assert "pytesseract is not installed" in result.error

    def test_pillow_not_installed(self, converter, tmp_path):
        fake_path = tmp_path / "video.mp4"
        fake_path.touch()

        with patch("builtins.__import__", side_effect=_import_blocker("PIL")):
            result = converter.convert(fake_path)

        assert result.success is False
        assert "Pillow is not installed" in result.error

    def test_video_failed_to_open(self, converter, tmp_path):
        fake_path = tmp_path / "bad.mp4"
        fake_path.touch()

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = converter.convert(fake_path)

        assert result.success is False
        assert "Failed to open video" in result.error

    def test_tesseract_not_found(self, converter, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        import pytesseract
        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string",
                   side_effect=pytesseract.TesseractNotFoundError()):
            result = converter.convert(video_file)

        assert result.success is False
        assert "Tesseract OCR engine is not installed" in result.error

    def test_generic_exception_during_conversion(self, converter, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=RuntimeError("CV2 crashed")):
            result = converter.convert(video_file)

        assert result.success is False
        assert "Failed to convert video" in result.error


class TestCustomInterval:
    def test_custom_frame_interval(self, converter_custom_interval, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        # 30 seconds at 30fps = 900 frames
        # With 10s interval: frames at 0, 10, 20 = 3 frames
        mock_cap = _make_mock_capture(fps=30.0, num_frames=900)
        call_count = [0]

        def counting_ocr(img, **kwargs):
            call_count[0] += 1
            return f"Text {call_count[0]}"

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", side_effect=counting_ocr):
            result = converter_custom_interval.convert(video_file)

        assert result.success is True
        assert "**Frames Analyzed:** 3" in result.markdown


class TestResultStructure:
    def test_result_source_path(self, converter, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=30)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value=""):
            result = converter.convert(video_file)

        assert result.source_path == video_file


class TestOcrLang:
    def test_ocr_lang_passed_to_pytesseract(self, tmp_path):
        converter = VideoConverter(ocr_lang="ell")
        video_file = tmp_path / "greek.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="Greek text") as mock_ocr:
            result = converter.convert(video_file)

        assert result.success is True
        assert mock_ocr.call_args[1]["lang"] == "ell"

    def test_ocr_lang_default_none(self, tmp_path):
        converter = VideoConverter()
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_cap = _make_mock_capture(fps=30.0, num_frames=150)

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch("cv2.cvtColor", side_effect=lambda f, c: f), \
             patch("pytesseract.image_to_string", return_value="English") as mock_ocr:
            result = converter.convert(video_file)

        assert result.success is True
        assert mock_ocr.call_args[1]["lang"] is None


class TestRegistration:
    def test_video_extensions_in_registry(self):
        from fileconverter.converters import CONVERTER_REGISTRY
        for ext in [".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv"]:
            assert ext in CONVERTER_REGISTRY
            assert CONVERTER_REGISTRY[ext] is VideoConverter

    def test_video_formats_in_supported(self):
        from fileconverter.converters import SUPPORTED_FORMATS
        for fmt in ["mp4", "avi", "mkv", "mov", "webm", "wmv"]:
            assert fmt in SUPPORTED_FORMATS

    def test_video_converter_in_all(self):
        from fileconverter import converters
        assert "VideoConverter" in converters.__all__


def _import_blocker(blocked_module):
    """Create an __import__ side_effect that blocks a specific module."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def blocker(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module + "."):
            raise ImportError(f"Mocked: {name} not installed")
        return real_import(name, *args, **kwargs)

    return blocker
