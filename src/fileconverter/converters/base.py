"""Base converter class and result dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConversionResult:
    """Result of a file conversion."""

    source_path: Path
    output_path: Path | None = None
    success: bool = False
    markdown: str = ""
    error: str | None = None
    images_extracted: list[Path] = field(default_factory=list)
    quality_score: float | None = None

    @property
    def filename(self) -> str:
        """Get the source filename."""
        return self.source_path.name


class BaseConverter(ABC):
    """Abstract base class for file converters."""

    def __init__(self, extract_images: bool = False):
        """Initialize converter.

        Args:
            extract_images: Whether to extract images from the document.
        """
        self.extract_images = extract_images

    @abstractmethod
    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a file to Markdown.

        Args:
            file_path: Path to the file to convert.

        Returns:
            ConversionResult with the conversion outcome.
        """
        pass

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        """Return list of supported file extensions."""
        pass

    def _create_error_result(self, file_path: Path, error: str) -> ConversionResult:
        """Create an error result."""
        return ConversionResult(
            source_path=file_path,
            success=False,
            error=error,
        )

    def _create_success_result(
        self,
        file_path: Path,
        markdown: str,
        images: list[Path] | None = None,
    ) -> ConversionResult:
        """Create a success result."""
        return ConversionResult(
            source_path=file_path,
            success=True,
            markdown=markdown,
            images_extracted=images or [],
        )
