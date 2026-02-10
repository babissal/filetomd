"""URL detection and filename utilities."""

import re
from pathlib import Path
from urllib.parse import urlparse


def is_url(value: str) -> bool:
    """Check if a string is an HTTP/HTTPS URL."""
    return value.startswith("http://") or value.startswith("https://")


def url_to_filename(url: str, max_length: int = 100) -> str:
    """Generate a filesystem-safe filename from a URL.

    Args:
        url: The URL to convert.
        max_length: Maximum length for the stem (before .md).

    Returns:
        A sanitized filename with .md extension.
    """
    parsed = urlparse(url)
    raw = parsed.netloc + parsed.path
    raw = raw.rstrip("/")
    # Replace unsafe chars with underscores
    safe = re.sub(r"[^\w.\-]", "_", raw)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_")
    if not safe:
        safe = "page"
    if len(safe) > max_length:
        safe = safe[:max_length]
    return safe + ".md"


def url_to_source_path(url: str) -> Path:
    """Create a Path representation for a URL.

    Used for ConversionResult.source_path display purposes.
    """
    parsed = urlparse(url)
    name = parsed.netloc + parsed.path.rstrip("/")
    return Path(name) if name else Path(url)
