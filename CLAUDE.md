# FileConverter

## Overview
Python CLI tool that converts documents and media files to Markdown, primarily for use as LLM context input. Built with Click.

## Project Structure
```
src/fileconverter/
  cli.py              # Click CLI entry point (main -> convert command)
  converter.py        # FileConverter orchestrator (batch, merge, parallel workers)
  converters/
    __init__.py        # CONVERTER_REGISTRY maps extensions -> converter classes
    base.py            # BaseConverter ABC + ConversionResult dataclass
    pdf.py             # pymupdf4llm extraction
    html.py            # markdownify + BeautifulSoup
    docx.py            # mammoth + markdownify
    xlsx.py            # openpyxl -> markdown tables
    csv.py             # auto-detect delimiter/encoding -> markdown tables
    msg.py             # extract-msg for Outlook emails
    pptx.py            # python-pptx for PowerPoint
    image.py           # Pillow + pytesseract OCR
    video.py           # OpenCV frame extraction + OCR
    url.py             # URL/web page fetching + readability extraction (extends HTMLConverter)
    table_postprocessor.py  # PDF table cleanup (degenerate detection, header inference)
  utils/
    file_utils.py      # File discovery and path utilities
    url_utils.py       # URL detection (is_url), filename generation, source_path helpers
tests/
  test_table_postprocessor.py
  test_image_converter.py
  test_video_converter.py
  test_url_converter.py
  test_merge.py
```

## Key Patterns
- **Converter registry**: `converters/__init__.py` maps file extensions to converter classes. To add a new format, create a converter class extending `BaseConverter`, then register it in `CONVERTER_REGISTRY`.
- **BaseConverter**: All converters implement `convert(file_path: Path) -> ConversionResult` and `supported_extensions() -> list[str]`. Use `_create_success_result()` / `_create_error_result()` helpers.
- **URLConverter**: Extends `HTMLConverter`, uses `convert_url(url, source_path)` instead of `convert()`. Not in `CONVERTER_REGISTRY` — routed explicitly by CLI via `is_url()` detection. Uses `_html_to_markdown()` shared method from HTMLConverter.
- **Entry point**: `fileconverter = "fileconverter.cli:main"` (defined in pyproject.toml)
- **Parallel processing**: `FileConverter.convert_batch()` uses `ThreadPoolExecutor` with configurable workers (default 4).

## Known Issues
- **pymupdf4llm threading**: `find_tables` can intermittently fail with `'NoneType' object has no attribute 'tables'` when processing multiple PDFs in parallel.
- **PDF flowcharts**: Swim-lane grid lines are misdetected as table cells, producing degenerate wide tables. The `table_postprocessor.py` module detects and restructures these (>=10 cols with high duplication or generic headers).
- **Non-adjacent cell splits**: Flowchart text split across non-adjacent cells (e.g., "YES" as "YE"..."S") cannot be reliably merged.

## Development
```bash
pip install -e ".[dev]"   # Install with dev dependencies
pytest                     # Run tests (configured in pyproject.toml: testpaths=tests, pythonpath=src)
```

## Tech Stack
- Python >=3.10, Click >=8.1
- PDF: pymupdf4llm | HTML: markdownify + beautifulsoup4 | DOCX: mammoth | XLSX: openpyxl
- MSG: extract-msg | PPTX: python-pptx | Images: Pillow + pytesseract | Video: opencv-python
- URL: requests + readability-lxml (Mozilla Readability for content extraction)
- External requirement: Tesseract OCR (for image/video conversion)
