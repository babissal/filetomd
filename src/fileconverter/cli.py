"""Click CLI interface for FileConverter."""

from pathlib import Path

import click

from fileconverter import __version__
from fileconverter.converter import FileConverter
from fileconverter.converters import SUPPORTED_FORMATS


@click.group()
@click.version_option(version=__version__, prog_name="fileconverter")
def main():
    """FileConverter - Convert documents to Markdown for LLM input.

    Supports PDF, HTML, DOCX, XLSX, MSG, CSV, PPTX, and image files
    (PNG, JPG, GIF, BMP, TIFF, WEBP).
    """
    pass


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for converted files. Default: same as source.",
)
@click.option(
    "-r", "--recursive",
    is_flag=True,
    help="Recursively process directories.",
)
@click.option(
    "-f", "--format",
    "formats",
    multiple=True,
    type=click.Choice(SUPPORTED_FORMATS, case_sensitive=False),
    help="Only convert specific formats. Can be specified multiple times.",
)
@click.option(
    "--extract-images",
    is_flag=True,
    help="Extract images from documents.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be converted without actually converting.",
)
@click.option(
    "-w", "--workers",
    type=int,
    default=4,
    help="Number of parallel workers for batch conversion.",
)
def convert(
    paths: tuple[str, ...],
    output: Path | None,
    recursive: bool,
    formats: tuple[str, ...],
    extract_images: bool,
    dry_run: bool,
    workers: int,
):
    """Convert files to Markdown.

    PATHS can be files or directories. Multiple paths can be specified.

    \b
    Examples:
        fileconverter convert document.pdf
        fileconverter convert doc1.pdf doc2.docx data.xlsx
        fileconverter convert ./documents/ -r -o ./markdown/
        fileconverter convert ./input/ --format pdf -r
        fileconverter convert ./documents/ -r --dry-run
    """
    # Convert path strings to Path objects
    path_list = [Path(p) for p in paths]

    # Create converter
    converter = FileConverter(
        output_dir=output,
        extract_images=extract_images,
        max_workers=workers,
    )

    # Convert formats tuple to list or None
    format_list = list(formats) if formats else None

    # Run conversion
    results = converter.convert_batch(
        path_list,
        recursive=recursive,
        formats=format_list,
        dry_run=dry_run,
    )

    if not results:
        click.echo("No files found to convert.")
        return

    # Display results
    success_count = 0
    error_count = 0

    if dry_run:
        click.echo("Dry run - files that would be converted:\n")

    for result in results:
        if result.success:
            success_count += 1
            if dry_run:
                click.echo(f"  {result.source_path}")
                click.echo(f"    -> {result.output_path}")
            else:
                click.echo(f"[OK] {result.source_path.name} -> {result.output_path}")
                if result.images_extracted:
                    click.echo(f"     Extracted {len(result.images_extracted)} images")
        else:
            error_count += 1
            click.echo(f"[ERROR] {result.source_path.name}: {result.error}", err=True)

    # Summary
    click.echo()
    if dry_run:
        click.echo(f"Would convert {success_count} file(s).")
    else:
        click.echo(f"Converted {success_count} file(s), {error_count} error(s).")


if __name__ == "__main__":
    main()
