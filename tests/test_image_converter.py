"""Tests for the ImageConverter."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from PIL import Image

from fileconverter.converters.image import ImageConverter


@pytest.fixture
def converter():
    return ImageConverter()


@pytest.fixture
def converter_extract():
    return ImageConverter(extract_images=True)


@pytest.fixture
def sample_image(tmp_path):
    """Create a simple test PNG image."""
    img = Image.new("RGB", (100, 50), "white")
    path = tmp_path / "test.png"
    img.save(path, format="PNG")
    img.close()
    return path


@pytest.fixture
def sample_bmp(tmp_path):
    """Create a BMP image (no format attribute when reopened without format)."""
    img = Image.new("L", (80, 40), 128)
    path = tmp_path / "gray.bmp"
    img.save(path, format="BMP")
    img.close()
    return path


class TestSupportedExtensions:
    def test_returns_all_image_extensions(self):
        exts = ImageConverter.supported_extensions()
        assert exts == [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"]

    def test_returns_list(self):
        assert isinstance(ImageConverter.supported_extensions(), list)


class TestConvertSuccess:
    def test_successful_conversion_with_text(self, converter, sample_image):
        with patch("pytesseract.image_to_string", return_value="Hello World"):
            result = converter.convert(sample_image)

        assert result.success is True
        assert "# Image: test.png" in result.markdown
        assert "**Format:** PNG" in result.markdown
        assert "**Size:** 100x50" in result.markdown
        assert "**Color Mode:** RGB" in result.markdown
        assert "## Extracted Text" in result.markdown
        assert "Hello World" in result.markdown

    def test_successful_conversion_no_text(self, converter, sample_image):
        with patch("pytesseract.image_to_string", return_value="   "):
            result = converter.convert(sample_image)

        assert result.success is True
        assert "*No text detected in image.*" in result.markdown
        assert "## Extracted Text" not in result.markdown

    def test_format_fallback_from_extension(self, converter, sample_bmp):
        """When img.format is None, falls back to extension."""
        mock_img = MagicMock()
        mock_img.size = (80, 40)
        mock_img.format = None
        mock_img.mode = "L"
        mock_img.__enter__ = lambda s: s
        mock_img.__exit__ = MagicMock(return_value=False)

        with patch("PIL.Image.open", return_value=mock_img), \
             patch("pytesseract.image_to_string", return_value=""):
            result = converter.convert(sample_bmp)

        assert result.success is True
        assert "**Format:** BMP" in result.markdown

    def test_images_not_extracted_by_default(self, converter, sample_image):
        with patch("pytesseract.image_to_string", return_value="text"):
            result = converter.convert(sample_image)

        assert result.images_extracted == []
        assert "![" not in result.markdown


class TestExtractImages:
    def test_extract_images_copies_file(self, converter_extract, sample_image):
        with patch("pytesseract.image_to_string", return_value="text"):
            result = converter_extract.convert(sample_image)

        assert result.success is True
        assert len(result.images_extracted) == 1

        dest = result.images_extracted[0]
        assert dest.exists()
        assert dest.name == "test.png"
        assert dest.parent.name == "test_images"

    def test_extract_images_embeds_reference(self, converter_extract, sample_image):
        with patch("pytesseract.image_to_string", return_value="text"):
            result = converter_extract.convert(sample_image)

        assert "![test.png]" in result.markdown


class TestErrorHandling:
    def test_pillow_not_installed(self, converter, tmp_path):
        fake_path = tmp_path / "img.png"
        fake_path.touch()

        with patch.dict(sys.modules, {"PIL": None, "PIL.Image": None}):
            # Need a fresh import to trigger the ImportError
            # Instead, mock the import inside convert
            with patch("builtins.__import__", side_effect=_import_blocker("PIL")):
                result = converter.convert(fake_path)

        assert result.success is False
        assert "Pillow is not installed" in result.error

    def test_pytesseract_not_installed(self, converter, tmp_path):
        fake_path = tmp_path / "img.png"
        fake_path.touch()

        with patch("builtins.__import__", side_effect=_import_blocker("pytesseract")):
            result = converter.convert(fake_path)

        assert result.success is False
        assert "pytesseract is not installed" in result.error

    def test_failed_to_open_image(self, converter, tmp_path):
        bad_file = tmp_path / "corrupt.png"
        bad_file.write_bytes(b"not an image")

        result = converter.convert(bad_file)

        assert result.success is False
        assert "Failed to open image" in result.error

    def test_tesseract_not_found(self, converter, sample_image):
        import pytesseract
        with patch("pytesseract.image_to_string",
                    side_effect=pytesseract.TesseractNotFoundError()):
            result = converter.convert(sample_image)

        assert result.success is False
        assert "Tesseract OCR engine is not installed" in result.error

    def test_generic_exception_during_conversion(self, converter, sample_image):
        with patch("pytesseract.image_to_string",
                    side_effect=RuntimeError("OCR crashed")):
            result = converter.convert(sample_image)

        assert result.success is False
        assert "Failed to convert image" in result.error
        assert "OCR crashed" in result.error


class TestResultStructure:
    def test_result_source_path(self, converter, sample_image):
        with patch("pytesseract.image_to_string", return_value=""):
            result = converter.convert(sample_image)

        assert result.source_path == sample_image

    def test_error_result_source_path(self, converter, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"nope")
        result = converter.convert(bad)
        assert result.source_path == bad


class TestOcrLang:
    def test_ocr_lang_passed_to_pytesseract(self, sample_image):
        converter = ImageConverter(ocr_lang="ell")
        with patch("pytesseract.image_to_string", return_value="Greek text") as mock_ocr:
            result = converter.convert(sample_image)

        assert result.success is True
        mock_ocr.assert_called_once()
        assert mock_ocr.call_args[1]["lang"] == "ell"

    def test_ocr_lang_default_none(self, sample_image):
        converter = ImageConverter()
        with patch("pytesseract.image_to_string", return_value="English text") as mock_ocr:
            result = converter.convert(sample_image)

        assert result.success is True
        mock_ocr.assert_called_once()
        assert mock_ocr.call_args[1]["lang"] is None

    def test_ocr_lang_multiple_languages(self, sample_image):
        converter = ImageConverter(ocr_lang="eng+fra")
        with patch("pytesseract.image_to_string", return_value="Bilingual") as mock_ocr:
            result = converter.convert(sample_image)

        assert result.success is True
        assert mock_ocr.call_args[1]["lang"] == "eng+fra"


class TestOcrEnhance:
    def test_ocr_enhance_calls_preprocessor(self, sample_image):
        converter = ImageConverter(ocr_enhance=True)
        with patch("pytesseract.image_to_string", return_value="Enhanced text"), \
             patch("fileconverter.converters.ocr_preprocessor.preprocess_for_ocr", return_value=Image.new("L", (100, 50))) as mock_preprocess:
            result = converter.convert(sample_image)

        assert result.success is True
        mock_preprocess.assert_called_once()

    def test_ocr_enhance_false_skips_preprocessor(self, sample_image):
        converter = ImageConverter(ocr_enhance=False)
        with patch("pytesseract.image_to_string", return_value="Normal text"), \
             patch("fileconverter.converters.ocr_preprocessor.preprocess_for_ocr") as mock_preprocess:
            result = converter.convert(sample_image)

        assert result.success is True
        mock_preprocess.assert_not_called()

    def test_ocr_enhance_default_false(self):
        converter = ImageConverter()
        assert converter.ocr_enhance is False

    def test_ocr_enhance_with_ocr_lang(self, sample_image):
        converter = ImageConverter(ocr_enhance=True, ocr_lang="ell")
        with patch("pytesseract.image_to_string", return_value="Greek text") as mock_ocr, \
             patch("fileconverter.converters.ocr_preprocessor.preprocess_for_ocr", return_value=Image.new("L", (100, 50))):
            result = converter.convert(sample_image)

        assert result.success is True
        assert mock_ocr.call_args[1]["lang"] == "ell"


class TestRegistration:
    def test_image_extensions_in_registry(self):
        from fileconverter.converters import CONVERTER_REGISTRY
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"]:
            assert ext in CONVERTER_REGISTRY
            assert CONVERTER_REGISTRY[ext] is ImageConverter

    def test_image_formats_in_supported(self):
        from fileconverter.converters import SUPPORTED_FORMATS
        for fmt in ["png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp"]:
            assert fmt in SUPPORTED_FORMATS

    def test_image_converter_in_all(self):
        from fileconverter import converters
        assert "ImageConverter" in converters.__all__


def _import_blocker(blocked_module):
    """Create an __import__ side_effect that blocks a specific module."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def blocker(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module + "."):
            raise ImportError(f"Mocked: {name} not installed")
        return real_import(name, *args, **kwargs)

    return blocker
