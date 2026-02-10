"""PDF to Markdown converter using pymupdf4llm."""

import time
from pathlib import Path

from fileconverter.converters.base import BaseConverter, ConversionResult
from fileconverter.converters.table_postprocessor import postprocess_tables


class PDFConverter(BaseConverter):
    """Convert PDF files to Markdown using pymupdf4llm."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".pdf"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a PDF file to Markdown.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            import pymupdf4llm
        except ImportError:
            return self._create_error_result(
                file_path,
                "pymupdf4llm is not installed. Run: pip install pymupdf4llm",
            )

        try:
            # pymupdf4llm.to_markdown handles tables and layout well.
            # Retry once on AttributeError — pymupdf4llm's find_tables has a
            # threading race condition that intermittently produces:
            #   "'NoneType' object has no attribute 'tables'"
            markdown = None
            for attempt in range(2):
                try:
                    markdown = pymupdf4llm.to_markdown(str(file_path))
                    break
                except AttributeError:
                    if attempt == 0:
                        time.sleep(0.5)
                    else:
                        raise

            # Post-process tables (fix degenerate tables, clean headers, etc.)
            markdown = postprocess_tables(markdown)

            # Clean up the markdown output
            markdown = self._clean_markdown(markdown)

            images: list[Path] = []
            if self.extract_images:
                images = self._extract_images(file_path)

            return self._create_success_result(file_path, markdown, images)

        except Exception as e:
            return self._create_error_result(file_path, str(e))

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

    def _extract_images(self, file_path: Path) -> list[Path]:
        """Extract images from PDF to the same directory."""
        images: list[Path] = []

        try:
            import pymupdf

            doc = pymupdf.open(str(file_path))
            output_dir = file_path.parent / f"{file_path.stem}_images"

            for page_num, page in enumerate(doc):
                image_list = page.get_images()

                for img_idx, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    output_dir.mkdir(exist_ok=True)
                    image_path = output_dir / f"page{page_num + 1}_img{img_idx + 1}.{image_ext}"
                    image_path.write_bytes(image_bytes)
                    images.append(image_path)

            doc.close()

        except Exception:
            # Image extraction is optional, don't fail conversion
            pass

        return images
