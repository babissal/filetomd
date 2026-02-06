"""Converter registry and exports."""

from fileconverter.converters.base import BaseConverter, ConversionResult
from fileconverter.converters.pdf import PDFConverter
from fileconverter.converters.html import HTMLConverter
from fileconverter.converters.docx import DOCXConverter
from fileconverter.converters.xlsx import XLSXConverter
from fileconverter.converters.msg import MSGConverter
from fileconverter.converters.csv import CSVConverter
from fileconverter.converters.pptx import PPTXConverter
from fileconverter.converters.image import ImageConverter

# Registry mapping file extensions to converter classes
CONVERTER_REGISTRY: dict[str, type[BaseConverter]] = {
    ".pdf": PDFConverter,
    ".html": HTMLConverter,
    ".htm": HTMLConverter,
    ".docx": DOCXConverter,
    ".xlsx": XLSXConverter,
    ".msg": MSGConverter,
    ".csv": CSVConverter,
    ".pptx": PPTXConverter,
    ".png": ImageConverter,
    ".jpg": ImageConverter,
    ".jpeg": ImageConverter,
    ".gif": ImageConverter,
    ".bmp": ImageConverter,
    ".tiff": ImageConverter,
    ".tif": ImageConverter,
    ".webp": ImageConverter,
}

# Supported formats for CLI help
SUPPORTED_FORMATS = [
    "pdf", "html", "htm", "docx", "xlsx", "msg", "csv", "pptx",
    "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp",
]


def get_converter(extension: str) -> type[BaseConverter] | None:
    """Get the converter class for a given file extension."""
    return CONVERTER_REGISTRY.get(extension.lower())


def get_supported_extensions() -> list[str]:
    """Get list of supported file extensions."""
    return list(CONVERTER_REGISTRY.keys())


__all__ = [
    "BaseConverter",
    "ConversionResult",
    "PDFConverter",
    "HTMLConverter",
    "DOCXConverter",
    "XLSXConverter",
    "MSGConverter",
    "CSVConverter",
    "PPTXConverter",
    "ImageConverter",
    "CONVERTER_REGISTRY",
    "SUPPORTED_FORMATS",
    "get_converter",
    "get_supported_extensions",
]
