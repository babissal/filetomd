"""URL/web page to Markdown converter."""

from pathlib import Path

from fileconverter.converters.html import HTMLConverter
from fileconverter.converters.base import ConversionResult


class URLConverter(HTMLConverter):
    """Convert web pages to Markdown by fetching and extracting main content."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; FileConverter/0.1)"

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return []

    def convert_url(self, url: str, source_path: Path) -> ConversionResult:
        """Fetch a URL and convert its main content to Markdown.

        Args:
            url: The URL to fetch.
            source_path: A Path representation for the URL (used in result).

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            import requests
        except ImportError:
            return self._create_error_result(
                source_path,
                "requests is not installed. Run: pip install requests",
            )

        try:
            from readability import Document
        except ImportError:
            return self._create_error_result(
                source_path,
                "readability-lxml is not installed. Run: pip install readability-lxml",
            )

        # Fetch the page
        try:
            response = requests.get(
                url,
                timeout=self.DEFAULT_TIMEOUT,
                headers={"User-Agent": self.DEFAULT_USER_AGENT},
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return self._create_error_result(source_path, f"Failed to fetch URL: {e}")

        # Extract main content with readability
        try:
            doc = Document(response.text)
            title = doc.title()
            content_html = doc.summary()
        except Exception as e:
            return self._create_error_result(
                source_path, f"Failed to extract content: {e}"
            )

        # Convert HTML to markdown using inherited method
        result = self._html_to_markdown(content_html, source_path)

        if result.success and title:
            result.markdown = f"# {title}\n\n{result.markdown}"

        return result
