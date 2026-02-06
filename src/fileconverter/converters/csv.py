"""CSV to Markdown converter."""

import csv
from pathlib import Path
from typing import Any

from fileconverter.converters.base import BaseConverter, ConversionResult


class CSVConverter(BaseConverter):
    """Convert CSV files to Markdown tables."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".csv"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a CSV file to Markdown table.

        Args:
            file_path: Path to the CSV file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            # Try to detect the encoding
            encoding = self._detect_encoding(file_path)

            # Read the CSV file
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                # Try to detect the dialect (delimiter, quoting, etc.)
                sample = f.read(8192)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample)
                    has_header = csv.Sniffer().has_header(sample)
                except csv.Error:
                    # Fall back to default dialect
                    dialect = csv.excel
                    has_header = True

                reader = csv.reader(f, dialect)
                rows = list(reader)

            if not rows:
                return self._create_error_result(file_path, "CSV file is empty")

            # Generate markdown table
            markdown = self._create_markdown_table(rows, has_header)

            return self._create_success_result(file_path, markdown)

        except Exception as e:
            return self._create_error_result(file_path, f"Failed to convert CSV: {str(e)}")

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect the file encoding."""
        # Try common encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read()
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue

        # Default to utf-8 if nothing works
        return 'utf-8'

    def _create_markdown_table(self, rows: list[list[str]], has_header: bool) -> str:
        """Create a markdown table from CSV rows.

        Args:
            rows: List of CSV rows.
            has_header: Whether the first row is a header.

        Returns:
            Markdown formatted table.
        """
        if not rows:
            return ""

        # Calculate column widths for better formatting
        col_count = max(len(row) for row in rows)
        col_widths = [0] * col_count

        # Normalize rows to have same number of columns
        normalized_rows = []
        for row in rows:
            normalized_row = list(row) + [''] * (col_count - len(row))
            normalized_rows.append(normalized_row)

            # Update column widths
            for i, cell in enumerate(normalized_row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Minimum width of 3 for alignment markers
        col_widths = [max(3, w) for w in col_widths]

        markdown_lines = []

        # Add filename as title
        # markdown_lines.append(f"# {file_path.stem}\n")

        # Process header
        if has_header and normalized_rows:
            header = normalized_rows[0]
            data_rows = normalized_rows[1:]

            # Header row
            header_cells = [self._pad_cell(cell, col_widths[i]) for i, cell in enumerate(header)]
            markdown_lines.append("| " + " | ".join(header_cells) + " |")

            # Separator row
            separators = ["-" * width for width in col_widths]
            markdown_lines.append("| " + " | ".join(separators) + " |")
        else:
            # No header, treat all as data
            data_rows = normalized_rows

            # Create generic header
            header_cells = [self._pad_cell(f"Column {i+1}", col_widths[i]) for i in range(col_count)]
            markdown_lines.append("| " + " | ".join(header_cells) + " |")

            # Separator row
            separators = ["-" * width for width in col_widths]
            markdown_lines.append("| " + " | ".join(separators) + " |")

        # Data rows
        for row in data_rows:
            cells = [self._pad_cell(cell, col_widths[i]) for i, cell in enumerate(row)]
            markdown_lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(markdown_lines)

    def _pad_cell(self, cell: str, width: int) -> str:
        """Pad a cell to the specified width.

        Args:
            cell: Cell content.
            width: Desired width.

        Returns:
            Padded cell content.
        """
        # Escape pipe characters in cell content
        cell = str(cell).replace('|', '\\|')
        # Pad to width
        return cell.ljust(width)
