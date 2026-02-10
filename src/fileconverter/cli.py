"""Click CLI interface for FileConverter."""

from pathlib import Path

import click

from fileconverter import __version__
from fileconverter.converter import FileConverter
from fileconverter.converters import SUPPORTED_FORMATS
from fileconverter.utils.url_utils import is_url


@click.group()
@click.version_option(version=__version__, prog_name="fileconverter")
def main():
    """FileConverter - Convert documents to Markdown for LLM input.

    Supports PDF, HTML, DOCX, XLSX, MSG, CSV, PPTX, image files
    (PNG, JPG, GIF, BMP, TIFF, WEBP), video files
    (MP4, AVI, MKV, MOV, WEBM, WMV), and URLs (HTTP/HTTPS).
    """
    pass


@main.command()
@click.argument("paths", nargs=-1, required=True)
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
@click.option(
    "-m", "--merge",
    is_flag=True,
    help="Merge all converted files into a single Markdown file.",
)
@click.option(
    "--merge-filename",
    type=str,
    default="merged.md",
    help="Filename for merged output. Default: merged.md.",
)
def convert(
    paths: tuple[str, ...],
    output: Path | None,
    recursive: bool,
    formats: tuple[str, ...],
    extract_images: bool,
    dry_run: bool,
    workers: int,
    merge: bool,
    merge_filename: str,
):
    """Convert files and URLs to Markdown.

    PATHS can be files, directories, or URLs. Multiple paths can be specified.

    \b
    Examples:
        fileconverter convert document.pdf
        fileconverter convert doc1.pdf doc2.docx data.xlsx
        fileconverter convert ./documents/ -r -o ./markdown/
        fileconverter convert ./input/ --format pdf -r
        fileconverter convert ./documents/ -r --dry-run
        fileconverter convert doc1.pdf doc2.docx --merge -o ./output/
        fileconverter convert ./docs/ -r --merge --merge-filename context.md
        fileconverter convert https://example.com/article
        fileconverter convert doc.pdf https://example.com/page --merge -o ./output/
    """
    # Separate URLs from file paths
    urls = [p for p in paths if is_url(p)]
    file_path_strings = [p for p in paths if not is_url(p)]

    # Validate file paths exist
    path_list: list[Path] = []
    for p in file_path_strings:
        path = Path(p)
        if not path.exists():
            raise click.BadParameter(
                f"Path '{p}' does not exist.", param_hint="'PATHS'"
            )
        path_list.append(path)

    # Create converter
    converter = FileConverter(
        output_dir=output,
        extract_images=extract_images,
        max_workers=workers,
    )

    # Convert formats tuple to list or None
    format_list = list(formats) if formats else None

    # Run conversion
    if merge:
        results = converter.convert_and_merge(
            path_list,
            recursive=recursive,
            formats=format_list,
            dry_run=dry_run,
            merge_filename=merge_filename,
            urls=urls,
        )
    else:
        # Convert files
        file_results = converter.convert_batch(
            path_list,
            recursive=recursive,
            formats=format_list,
            dry_run=dry_run,
        ) if path_list else []

        # Convert URLs
        url_results = converter.convert_urls(
            urls,
            dry_run=dry_run,
        ) if urls else []

        results = file_results + url_results

    if not results:
        click.echo("No files found to convert.")
        return

    # Display results
    success_count = 0
    error_count = 0

    if dry_run and merge:
        merged_path = results[0].output_path if results else merge_filename
        click.echo(f"Dry run - files that would be merged into {merged_path}:\n")
    elif dry_run:
        click.echo("Dry run - files that would be converted:\n")

    for result in results:
        if result.success:
            success_count += 1
            if dry_run:
                click.echo(f"  {result.source_path}")
                if not merge:
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
    if dry_run and merge:
        click.echo(f"Would merge {success_count} file(s) into {merged_path}.")
    elif dry_run:
        click.echo(f"Would convert {success_count} file(s).")
    elif merge:
        merged_path = results[0].output_path if results and results[0].success else merge_filename
        click.echo(f"Merged {success_count} file(s) into {merged_path}, {error_count} error(s).")
    else:
        click.echo(f"Converted {success_count} file(s), {error_count} error(s).")


if __name__ == "__main__":
    main()
