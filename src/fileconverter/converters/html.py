"""HTML to Markdown converter using markdownify and BeautifulSoup."""

from pathlib import Path

from fileconverter.converters.base import BaseConverter, ConversionResult


class HTMLConverter(BaseConverter):
    """Convert HTML files to Markdown using markdownify."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".html", ".htm"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert an HTML file to Markdown.

        Args:
            file_path: Path to the HTML file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            html_content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return self._create_error_result(file_path, str(e))

        return self._html_to_markdown(html_content, file_path)

    def _html_to_markdown(self, html_content: str, source_path: Path) -> ConversionResult:
        """Convert an HTML string to Markdown.

        Args:
            html_content: Raw HTML string.
            source_path: Source identifier for the result.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md
        except ImportError as e:
            return self._create_error_result(
                source_path,
                f"Required package not installed: {e}. Run: pip install markdownify beautifulsoup4",
            )

        try:
            # Parse with BeautifulSoup to clean up
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "noscript"]):
                element.decompose()

            # Get the body content if present, otherwise use whole document
            body = soup.body if soup.body else soup

            # Convert to markdown
            markdown = md(
                str(body),
                heading_style="atx",
                bullets="-",
                strip=["script", "style"],
            )

            # Clean up the output
            markdown = self._clean_markdown(markdown)

            return self._create_success_result(source_path, markdown)

        except Exception as e:
            return self._create_error_result(source_path, str(e))

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up the markdown output."""
        # Remove excessive blank lines
        lines = markdown.split("\n")
        cleaned_lines: list[str] = []
        prev_blank = False

        for line in lines:
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            cleaned_lines.append(line)
            prev_blank = is_blank

        return "\n".join(cleaned_lines).strip()
