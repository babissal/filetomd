"""File discovery and path utilities."""

from pathlib import Path

from fileconverter.converters import get_supported_extensions


def discover_files(
    paths: list[Path],
    recursive: bool = False,
    formats: list[str] | None = None,
) -> list[Path]:
    """Discover all convertible files from the given paths.

    Args:
        paths: List of file or directory paths.
        recursive: Whether to search directories recursively.
        formats: Optional list of formats to filter by (e.g., ["pdf", "docx"]).

    Returns:
        List of file paths to convert.
    """
    # Determine which extensions to look for
    if formats:
        extensions = {f".{fmt.lower().lstrip('.')}" for fmt in formats}
    else:
        extensions = set(get_supported_extensions())

    discovered: list[Path] = []

    for path in paths:
        if path.is_file():
            if path.suffix.lower() in extensions:
                discovered.append(path)
        elif path.is_dir():
            if recursive:
                for ext in extensions:
                    discovered.extend(path.rglob(f"*{ext}"))
            else:
                for ext in extensions:
                    discovered.extend(path.glob(f"*{ext}"))

    # Remove duplicates and sort
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in discovered:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)

    return sorted(unique, key=lambda p: p.name.lower())


def get_output_path(
    source_path: Path,
    output_dir: Path | None = None,
    source_base: Path | None = None,
) -> Path:
    """Get the output path for a converted file.

    Args:
        source_path: Path to the source file.
        output_dir: Optional output directory. If None, uses source directory.
        source_base: Base directory for preserving relative paths in batch mode.

    Returns:
        Path for the output markdown file.
    """
    # Change extension to .md
    output_name = source_path.stem + ".md"

    if output_dir is None:
        # Output to same directory as source
        return source_path.parent / output_name

    # If source_base is provided, preserve relative directory structure
    if source_base is not None:
        try:
            relative = source_path.parent.relative_to(source_base)
            target_dir = output_dir / relative
        except ValueError:
            # source_path is not relative to source_base
            target_dir = output_dir
    else:
        target_dir = output_dir

    return target_dir / output_name
