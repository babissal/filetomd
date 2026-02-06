"""MSG to Markdown converter for Outlook email messages."""

from pathlib import Path
from datetime import datetime

from fileconverter.converters.base import BaseConverter, ConversionResult


class MSGConverter(BaseConverter):
    """Convert MSG (Outlook email) files to Markdown."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".msg"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert an MSG file to Markdown.

        Args:
            file_path: Path to the MSG file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            import extract_msg
        except ImportError as e:
            return self._create_error_result(
                file_path,
                f"Required package not installed: {e}. Run: pip install extract-msg",
            )

        try:
            # Open the MSG file
            msg = extract_msg.Message(str(file_path))

            # Build markdown content
            markdown_parts = []

            # Add email metadata as a header
            markdown_parts.append("# Email Message\n")

            # Add metadata fields
            if msg.subject:
                markdown_parts.append(f"**Subject:** {msg.subject}\n")

            if msg.sender:
                markdown_parts.append(f"**From:** {msg.sender}\n")

            if msg.to:
                markdown_parts.append(f"**To:** {msg.to}\n")

            if msg.cc:
                markdown_parts.append(f"**CC:** {msg.cc}\n")

            if msg.date:
                # Format the date nicely
                try:
                    date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if isinstance(msg.date, datetime) else str(msg.date)
                    markdown_parts.append(f"**Date:** {date_str}\n")
                except:
                    markdown_parts.append(f"**Date:** {msg.date}\n")

            markdown_parts.append("\n---\n\n")

            # Add email body
            # Try to get HTML body first, then plain text
            body = msg.htmlBody or msg.body or ""

            if msg.htmlBody:
                # Convert HTML to markdown if we have HTML body
                try:
                    from markdownify import markdownify as md
                    body = md(body, heading_style="atx", bullets="-")
                except ImportError:
                    # If markdownify is not available, use plain text
                    body = msg.body or ""

            markdown_parts.append(body)

            # Handle attachments
            attachments_list: list[Path] = []

            if msg.attachments:
                markdown_parts.append("\n\n---\n\n## Attachments\n")

                # Create attachments directory if we're extracting
                if self.extract_images:
                    attachments_dir = file_path.parent / f"{file_path.stem}_attachments"
                    attachments_dir.mkdir(exist_ok=True)

                    for i, attachment in enumerate(msg.attachments):
                        try:
                            # Get attachment filename
                            filename = attachment.longFilename or attachment.shortFilename or f"attachment_{i+1}"

                            # Save the attachment
                            attachment_path = attachments_dir / filename
                            attachment.save(customPath=str(attachments_dir), customFilename=filename)
                            attachments_list.append(attachment_path)

                            # Check if it's an image and add it as an embedded image in markdown
                            if self._is_image_file(filename):
                                markdown_parts.append(f"\n### {filename}\n")
                                markdown_parts.append(f"![{filename}]({attachment_path})\n")
                            else:
                                markdown_parts.append(f"- [{filename}]({attachment_path})\n")

                        except Exception as e:
                            markdown_parts.append(f"- ⚠️ Failed to extract: {filename} ({str(e)})\n")
                else:
                    # Just list attachment names without extracting
                    for i, attachment in enumerate(msg.attachments):
                        filename = attachment.longFilename or attachment.shortFilename or f"attachment_{i+1}"
                        markdown_parts.append(f"- {filename}\n")

            # Close the message
            msg.close()

            # Combine all parts into final markdown
            markdown = "".join(markdown_parts).strip()

            # Clean up the markdown
            markdown = self._clean_markdown(markdown)

            return self._create_success_result(file_path, markdown, attachments_list)

        except Exception as e:
            return self._create_error_result(file_path, f"Failed to convert MSG file: {str(e)}")

    def _is_image_file(self, filename: str) -> bool:
        """Check if a file is an image based on its extension."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.ico', '.svg'}
        return Path(filename).suffix.lower() in image_extensions

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up the markdown output."""
        # Remove excessive blank lines (more than 2 consecutive)
        lines = markdown.split("\n")
        cleaned_lines: list[str] = []
        blank_count = 0

        for line in lines:
            is_blank = not line.strip()
            if is_blank:
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append(line)
            else:
                blank_count = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()
