"""Tests for the OCR preprocessing pipeline."""

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from fileconverter.converters.ocr_preprocessor import (
    MIN_WIDTH_FOR_UPSCALE,
    UPSCALE_FACTOR,
    preprocess_for_ocr,
    _preprocess_pillow_only,
    _upscale_if_small,
)


class TestPreprocessForOcr:
    def test_returns_pil_image(self):
        img = Image.new("RGB", (800, 600), "white")
        result = preprocess_for_ocr(img)
        assert isinstance(result, Image.Image)

    def test_output_is_grayscale(self):
        img = Image.new("RGB", (1200, 800), "white")
        result = preprocess_for_ocr(img)
        assert result.mode == "L"

    def test_small_image_is_upscaled(self):
        img = Image.new("RGB", (500, 300), "white")
        result = preprocess_for_ocr(img)
        # 500 < 1000 -> upscaled by 2x -> 1000 width minimum
        assert result.width >= 500 * UPSCALE_FACTOR

    def test_large_image_not_upscaled(self):
        img = Image.new("RGB", (2000, 1500), "white")
        result = preprocess_for_ocr(img)
        # Should not be bigger than original
        assert result.width <= 2000

    def test_accepts_grayscale_input(self):
        img = Image.new("L", (1200, 800), 128)
        result = preprocess_for_ocr(img)
        assert isinstance(result, Image.Image)
        assert result.mode == "L"

    def test_accepts_rgba_input(self):
        img = Image.new("RGBA", (1200, 800), (255, 0, 0, 128))
        result = preprocess_for_ocr(img)
        assert isinstance(result, Image.Image)
        assert result.mode == "L"

    def test_does_not_modify_original(self):
        img = Image.new("RGB", (1200, 800), "red")
        original_mode = img.mode
        original_size = img.size
        preprocess_for_ocr(img)
        assert img.mode == original_mode
        assert img.size == original_size


class TestUpscaleIfSmall:
    def test_below_threshold_is_upscaled(self):
        img = Image.new("L", (MIN_WIDTH_FOR_UPSCALE - 1, 400))
        result = _upscale_if_small(img)
        assert result.width == (MIN_WIDTH_FOR_UPSCALE - 1) * UPSCALE_FACTOR

    def test_at_threshold_not_upscaled(self):
        img = Image.new("L", (MIN_WIDTH_FOR_UPSCALE, 400))
        result = _upscale_if_small(img)
        assert result.width == MIN_WIDTH_FOR_UPSCALE

    def test_above_threshold_not_upscaled(self):
        img = Image.new("L", (MIN_WIDTH_FOR_UPSCALE + 100, 400))
        result = _upscale_if_small(img)
        assert result.width == MIN_WIDTH_FOR_UPSCALE + 100

    def test_height_also_scaled(self):
        img = Image.new("L", (500, 300))
        result = _upscale_if_small(img)
        assert result.height == 300 * UPSCALE_FACTOR


class TestPillowOnlyFallback:
    def test_returns_grayscale(self):
        img = Image.new("RGB", (1200, 800), "blue")
        result = _preprocess_pillow_only(img)
        assert result.mode == "L"

    def test_returns_pil_image(self):
        img = Image.new("RGB", (1200, 800), "white")
        result = _preprocess_pillow_only(img)
        assert isinstance(result, Image.Image)

    def test_triggered_when_cv2_missing(self):
        img = Image.new("RGB", (1200, 800), "white")
        with patch.dict("sys.modules", {"cv2": None}):
            with patch("builtins.__import__", side_effect=_cv2_blocker()):
                result = preprocess_for_ocr(img)
        assert isinstance(result, Image.Image)
        assert result.mode == "L"


class TestOpenCVSteps:
    def test_denoise_called(self):
        img = Image.new("RGB", (1200, 800), "white")
        with patch("fileconverter.converters.ocr_preprocessor._denoise", return_value=__import__("numpy").zeros((800, 1200), dtype=__import__("numpy").uint8)) as mock_denoise:
            preprocess_for_ocr(img)
        mock_denoise.assert_called_once()

    def test_clahe_called(self):
        img = Image.new("RGB", (1200, 800), "white")
        with patch("fileconverter.converters.ocr_preprocessor._apply_clahe", return_value=__import__("numpy").zeros((800, 1200), dtype=__import__("numpy").uint8)) as mock_clahe:
            preprocess_for_ocr(img)
        mock_clahe.assert_called_once()

    def test_binarize_called(self):
        img = Image.new("RGB", (1200, 800), "white")
        with patch("fileconverter.converters.ocr_preprocessor._binarize", return_value=__import__("numpy").zeros((800, 1200), dtype=__import__("numpy").uint8)) as mock_bin:
            preprocess_for_ocr(img)
        mock_bin.assert_called_once()

    def test_deskew_called(self):
        img = Image.new("RGB", (1200, 800), "white")
        with patch("fileconverter.converters.ocr_preprocessor._deskew", return_value=__import__("numpy").zeros((800, 1200), dtype=__import__("numpy").uint8)) as mock_deskew:
            preprocess_for_ocr(img)
        mock_deskew.assert_called_once()


def _cv2_blocker():
    """Create an __import__ side_effect that blocks cv2."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def blocker(name, *args, **kwargs):
        if name == "cv2" or name.startswith("cv2."):
            raise ImportError("Mocked: cv2 not installed")
        return real_import(name, *args, **kwargs)

    return blocker
