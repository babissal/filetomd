"""Image to Markdown converter using OCR."""

import shutil
from pathlib import Path

from fileconverter.converters.base import BaseConverter, ConversionResult


class ImageConverter(BaseConverter):
    """Convert image files to Markdown using OCR text extraction."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert an image file to Markdown via OCR.

        Args:
            file_path: Path to the image file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            from PIL import Image
        except ImportError:
            return self._create_error_result(
                file_path,
                "Pillow is not installed. Run: pip install Pillow",
            )

        try:
            import pytesseract
        except ImportError:
            return self._create_error_result(
                file_path,
                "pytesseract is not installed. Run: pip install pytesseract",
            )

        try:
            img = Image.open(file_path)
        except Exception as e:
            return self._create_error_result(
                file_path, f"Failed to open image: {e}"
            )

        try:
            # Gather metadata
            width, height = img.size
            image_format = img.format or file_path.suffix.lstrip(".").upper()
            color_mode = img.mode

            # Run OCR
            try:
                ocr_text = pytesseract.image_to_string(img).strip()
            except pytesseract.TesseractNotFoundError:
                return self._create_error_result(
                    file_path,
                    "Tesseract OCR engine is not installed. "
                    "Install it from https://github.com/tesseract-ocr/tesseract "
                    "and ensure it is on your PATH.",
                )

            # Build markdown
            lines = [
                f"# Image: {file_path.name}",
                "",
                f"**Format:** {image_format} | **Size:** {width}x{height} | **Color Mode:** {color_mode}",
                "",
            ]

            if ocr_text:
                lines.append("## Extracted Text")
                lines.append("")
                lines.append(ocr_text)
            else:
                lines.append("*No text detected in image.*")

            # Handle extract_images: copy original image and embed reference
            images: list[Path] = []
            if self.extract_images:
                output_dir = file_path.parent / f"{file_path.stem}_images"
                output_dir.mkdir(exist_ok=True)
                dest = output_dir / file_path.name
                shutil.copy2(file_path, dest)
                images.append(dest)

                lines.append("")
                lines.append(f"![{file_path.name}]({dest.name})")

            markdown = "\n".join(lines)
            return self._create_success_result(file_path, markdown, images)

        except Exception as e:
            return self._create_error_result(
                file_path, f"Failed to convert image: {e}"
            )
        finally:
            img.close()
