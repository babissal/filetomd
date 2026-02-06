"""DOCX to Markdown converter using mammoth and markdownify."""

from pathlib import Path

from fileconverter.converters.base import BaseConverter, ConversionResult


class DOCXConverter(BaseConverter):
    """Convert DOCX files to Markdown using mammoth."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".docx"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a DOCX file to Markdown.

        Args:
            file_path: Path to the DOCX file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            import mammoth
            from markdownify import markdownify as md
        except ImportError as e:
            return self._create_error_result(
                file_path,
                f"Required package not installed: {e}. Run: pip install mammoth markdownify",
            )

        try:
            images: list[Path] = []
            image_handler = None

            if self.extract_images:
                output_dir = file_path.parent / f"{file_path.stem}_images"
                image_counter = [0]  # Use list to allow mutation in closure

                def handle_image(image):
                    image_counter[0] += 1
                    extension = image.content_type.split("/")[-1]
                    if extension == "jpeg":
                        extension = "jpg"

                    output_dir.mkdir(exist_ok=True)
                    image_path = output_dir / f"image_{image_counter[0]}.{extension}"

                    with image.open() as img_stream:
                        image_path.write_bytes(img_stream.read())

                    images.append(image_path)
                    return {"src": str(image_path)}

                image_handler = handle_image

            # Convert DOCX to HTML using mammoth
            with open(file_path, "rb") as docx_file:
                if image_handler:
                    result = mammoth.convert_to_html(
                        docx_file,
                        convert_image=mammoth.images.img_element(image_handler),
                    )
                else:
                    result = mammoth.convert_to_html(docx_file)

            html_content = result.value

            # Convert HTML to Markdown
            markdown = md(
                html_content,
                heading_style="atx",
                bullets="-",
            )

            # Clean up the output
            markdown = self._clean_markdown(markdown)

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
