"""Tests for the URLConverter and URL utilities."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fileconverter.converters.url import URLConverter
from fileconverter.utils.url_utils import is_url, url_to_filename, url_to_source_path


# --- URLConverter tests ---


@pytest.fixture
def converter():
    return URLConverter()


class TestConvertUrlSuccess:
    def test_successful_conversion(self, converter):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello world</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_doc = MagicMock()
        mock_doc.title.return_value = "Test Page"
        mock_doc.summary.return_value = "<p>Hello world</p>"

        source = Path("example.com/page")

        with patch("requests.get", return_value=mock_response), \
             patch("readability.Document", return_value=mock_doc):
            result = converter.convert_url("https://example.com/page", source)

        assert result.success is True
        assert "Hello world" in result.markdown

    def test_title_prepended(self, converter):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_doc = MagicMock()
        mock_doc.title.return_value = "My Title"
        mock_doc.summary.return_value = "<p>Content</p>"

        source = Path("example.com/page")

        with patch("requests.get", return_value=mock_response), \
             patch("readability.Document", return_value=mock_doc):
            result = converter.convert_url("https://example.com/page", source)

        assert result.success is True
        assert result.markdown.startswith("# My Title\n\n")

    def test_empty_title_not_prepended(self, converter):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_doc = MagicMock()
        mock_doc.title.return_value = ""
        mock_doc.summary.return_value = "<p>Content</p>"

        source = Path("example.com/page")

        with patch("requests.get", return_value=mock_response), \
             patch("readability.Document", return_value=mock_doc):
            result = converter.convert_url("https://example.com/page", source)

        assert result.success is True
        assert not result.markdown.startswith("# ")


class TestConvertUrlErrors:
    def test_http_error(self, converter):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("404")

        source = Path("example.com/missing")

        with patch("requests.get", return_value=mock_response):
            result = converter.convert_url("https://example.com/missing", source)

        assert result.success is False
        assert "Failed to fetch URL" in result.error

    def test_timeout_error(self, converter):
        import requests as req

        source = Path("example.com/slow")

        with patch("requests.get", side_effect=req.exceptions.Timeout("timeout")):
            result = converter.convert_url("https://example.com/slow", source)

        assert result.success is False
        assert "Failed to fetch URL" in result.error

    def test_connection_error(self, converter):
        import requests as req

        source = Path("example.com/down")

        with patch("requests.get", side_effect=req.exceptions.ConnectionError("refused")):
            result = converter.convert_url("https://example.com/down", source)

        assert result.success is False
        assert "Failed to fetch URL" in result.error

    def test_readability_extraction_error(self, converter):
        mock_response = MagicMock()
        mock_response.text = "<html><body>bad</body></html>"
        mock_response.raise_for_status = MagicMock()

        source = Path("example.com/bad")

        with patch("requests.get", return_value=mock_response), \
             patch("readability.Document", side_effect=Exception("parse error")):
            result = converter.convert_url("https://example.com/bad", source)

        assert result.success is False
        assert "Failed to extract content" in result.error

    def test_supported_extensions_empty(self, converter):
        assert converter.supported_extensions() == []


# --- URL utility tests ---


class TestIsUrl:
    def test_https(self):
        assert is_url("https://example.com") is True

    def test_http(self):
        assert is_url("http://example.com/page") is True

    def test_file_path(self):
        assert is_url("document.pdf") is False

    def test_relative_path(self):
        assert is_url("./path/to/file") is False

    def test_windows_path(self):
        assert is_url("C:\\Users\\doc.pdf") is False

    def test_empty_string(self):
        assert is_url("") is False


class TestUrlToFilename:
    def test_simple_url(self):
        result = url_to_filename("https://example.com/blog/article-123")
        assert result == "example.com_blog_article-123.md"

    def test_trailing_slash(self):
        result = url_to_filename("https://example.com/page/")
        assert result == "example.com_page.md"

    def test_root_url(self):
        result = url_to_filename("https://example.com/")
        assert result == "example.com.md"

    def test_truncation(self):
        long_url = "https://example.com/" + "a" * 200
        result = url_to_filename(long_url, max_length=50)
        stem = result[:-3]  # remove .md
        assert len(stem) <= 50

    def test_special_characters(self):
        result = url_to_filename("https://example.com/page?q=hello&lang=en")
        assert ".md" in result
        # Should not contain ? or &
        assert "?" not in result
        assert "&" not in result


class TestUrlToSourcePath:
    def test_simple_url(self):
        result = url_to_source_path("https://example.com/article")
        assert result.name == "article"

    def test_root_url(self):
        result = url_to_source_path("https://example.com/")
        assert "example.com" in str(result)
