"""Main orchestrator for file conversion."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fileconverter.converters import get_converter
from fileconverter.converters.base import ConversionResult
from fileconverter.utils.file_utils import discover_files, get_output_path


class FileConverter:
    """Main orchestrator for converting files to Markdown."""

    def __init__(
        self,
        output_dir: Path | None = None,
        extract_images: bool = False,
        max_workers: int = 4,
    ):
        """Initialize the converter.

        Args:
            output_dir: Directory to write output files. None = same as source.
            extract_images: Whether to extract images from documents.
            max_workers: Maximum number of parallel conversion threads.
        """
        self.output_dir = output_dir
        self.extract_images = extract_images
        self.max_workers = max_workers

    def convert_file(self, file_path: Path) -> ConversionResult:
        """Convert a single file to Markdown.

        Args:
            file_path: Path to the file to convert.

        Returns:
            ConversionResult with the conversion outcome.
        """
        extension = file_path.suffix.lower()
        converter_class = get_converter(extension)

        if converter_class is None:
            return ConversionResult(
                source_path=file_path,
                success=False,
                error=f"Unsupported file format: {extension}",
            )

        converter = converter_class(extract_images=self.extract_images)
        result = converter.convert(file_path)

        return result

    def convert_and_save(
        self,
        file_path: Path,
        source_base: Path | None = None,
    ) -> ConversionResult:
        """Convert a file and save the output.

        Args:
            file_path: Path to the file to convert.
            source_base: Base directory for preserving relative paths.

        Returns:
            ConversionResult with output_path set if successful.
        """
        result = self.convert_file(file_path)

        if result.success:
            output_path = get_output_path(file_path, self.output_dir, source_base)

            # Create output directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the markdown
            output_path.write_text(result.markdown, encoding="utf-8")
            result.output_path = output_path

        return result

    def convert_batch(
        self,
        paths: list[Path],
        recursive: bool = False,
        formats: list[str] | None = None,
        dry_run: bool = False,
    ) -> list[ConversionResult]:
        """Convert multiple files or directories.

        Args:
            paths: List of file or directory paths to convert.
            recursive: Whether to search directories recursively.
            formats: Optional list of formats to filter by.
            dry_run: If True, only return what would be converted.

        Returns:
            List of ConversionResults.
        """
        # Discover all files
        files = discover_files(paths, recursive=recursive, formats=formats)

        if not files:
            return []

        # Determine source base for preserving directory structure
        source_base = None
        if len(paths) == 1 and paths[0].is_dir():
            source_base = paths[0]

        if dry_run:
            # Return results showing what would be converted
            results: list[ConversionResult] = []
            for file_path in files:
                output_path = get_output_path(file_path, self.output_dir, source_base)
                results.append(ConversionResult(
                    source_path=file_path,
                    output_path=output_path,
                    success=True,
                    markdown="[dry run]",
                ))
            return results

        # Convert files in parallel
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self.convert_and_save, f, source_base): f
                for f in files
            }

            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)

        # Sort results by filename for consistent output
        results.sort(key=lambda r: r.source_path.name.lower())

        return results

    def convert_and_merge(
        self,
        paths: list[Path],
        recursive: bool = False,
        formats: list[str] | None = None,
        dry_run: bool = False,
        merge_filename: str = "merged.md",
    ) -> list[ConversionResult]:
        """Convert multiple files and merge into a single Markdown file.

        Individual .md files are NOT written. Only the merged output is saved.

        Args:
            paths: List of file or directory paths to convert.
            recursive: Whether to search directories recursively.
            formats: Optional list of formats to filter by.
            dry_run: If True, only return what would be merged.
            merge_filename: Name of the merged output file.

        Returns:
            List of ConversionResults (one per source file).
        """
        # Discover all files
        files = discover_files(paths, recursive=recursive, formats=formats)

        if not files:
            return []

        # Determine merged output path
        if self.output_dir is not None:
            merged_path = self.output_dir / merge_filename
        else:
            merged_path = Path.cwd() / merge_filename

        if dry_run:
            results: list[ConversionResult] = []
            for file_path in files:
                results.append(ConversionResult(
                    source_path=file_path,
                    output_path=merged_path,
                    success=True,
                    markdown="[dry run]",
                ))
            return results

        # Convert files in parallel (without writing individual files)
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self.convert_file, f): f
                for f in files
            }

            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)

        # Sort results by filename for deterministic output
        results.sort(key=lambda r: r.source_path.name.lower())

        # Build merged markdown from successful conversions
        sections: list[str] = []
        for result in results:
            if result.success:
                sections.append(f"# {result.filename}\n\n{result.markdown}")

        if sections:
            merged_content = "\n\n---\n\n".join(sections) + "\n"

            # Write merged file
            merged_path.parent.mkdir(parents=True, exist_ok=True)
            merged_path.write_text(merged_content, encoding="utf-8")

            # Set output_path on successful results
            for result in results:
                if result.success:
                    result.output_path = merged_path

        return results
