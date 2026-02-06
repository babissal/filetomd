"""Tests for the merge mode feature."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fileconverter.converter import FileConverter
from fileconverter.converters.base import ConversionResult


def _make_fake_convert(results_map: dict[str, ConversionResult]):
    """Create a fake convert_file that returns pre-defined results by filename."""

    def fake_convert_file(self, file_path: Path) -> ConversionResult:
        name = file_path.name
        if name in results_map:
            return results_map[name]
        return ConversionResult(
            source_path=file_path,
            success=False,
            error=f"Unsupported file format: {file_path.suffix}",
        )

    return fake_convert_file


class TestMergedOutput:
    def test_merged_output_contains_all_documents(self, tmp_path):
        """Merged file should contain all documents with headers and separators."""
        # Create fake source files
        src = tmp_path / "src"
        src.mkdir()
        (src / "alpha.pdf").touch()
        (src / "beta.docx").touch()

        results_map = {
            "alpha.pdf": ConversionResult(
                source_path=src / "alpha.pdf",
                success=True,
                markdown="Alpha content here.",
            ),
            "beta.docx": ConversionResult(
                source_path=src / "beta.docx",
                success=True,
                markdown="Beta content here.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            results = converter.convert_and_merge([src], recursive=False)

        # Verify merged file was written
        merged = out / "merged.md"
        assert merged.exists()

        content = merged.read_text(encoding="utf-8")

        # Both documents present with headers
        assert "# alpha.pdf" in content
        assert "Alpha content here." in content
        assert "# beta.docx" in content
        assert "Beta content here." in content

        # Separator between documents
        assert "---" in content

        # Sorted alphabetically: alpha before beta
        alpha_pos = content.index("# alpha.pdf")
        beta_pos = content.index("# beta.docx")
        assert alpha_pos < beta_pos

    def test_merged_output_structure(self, tmp_path):
        """Verify the exact structure: header, content, separator."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "one.pdf").touch()
        (src / "two.pdf").touch()

        results_map = {
            "one.pdf": ConversionResult(
                source_path=src / "one.pdf",
                success=True,
                markdown="Content one.",
            ),
            "two.pdf": ConversionResult(
                source_path=src / "two.pdf",
                success=True,
                markdown="Content two.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            converter.convert_and_merge([src], recursive=False)

        content = (out / "merged.md").read_text(encoding="utf-8")
        expected = "# one.pdf\n\nContent one.\n\n---\n\n# two.pdf\n\nContent two.\n"
        assert content == expected


class TestFailedFilesExcluded:
    def test_failed_files_are_excluded_from_merged_output(self, tmp_path):
        """Failed conversions should not appear in the merged file."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "good.pdf").touch()
        (src / "bad.docx").touch()

        results_map = {
            "good.pdf": ConversionResult(
                source_path=src / "good.pdf",
                success=True,
                markdown="Good content.",
            ),
            "bad.docx": ConversionResult(
                source_path=src / "bad.docx",
                success=False,
                error="Conversion failed",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            results = converter.convert_and_merge([src], recursive=False)

        content = (out / "merged.md").read_text(encoding="utf-8")

        # Good file is included
        assert "# good.pdf" in content
        assert "Good content." in content

        # Bad file is NOT in merged output
        assert "bad.docx" not in content

        # But the error is still reported in results
        error_results = [r for r in results if not r.success]
        assert len(error_results) == 1
        assert error_results[0].error == "Conversion failed"

    def test_all_files_fail_produces_no_merged_file(self, tmp_path):
        """If all conversions fail, no merged file should be written."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.pdf").touch()

        results_map = {
            "bad.pdf": ConversionResult(
                source_path=src / "bad.pdf",
                success=False,
                error="Conversion failed",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            results = converter.convert_and_merge([src], recursive=False)

        assert not (out / "merged.md").exists()
        assert len(results) == 1
        assert not results[0].success


class TestMergeFilename:
    def test_custom_merge_filename(self, tmp_path):
        """--merge-filename should override the default name."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.pdf").touch()

        results_map = {
            "doc.pdf": ConversionResult(
                source_path=src / "doc.pdf",
                success=True,
                markdown="Doc content.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            results = converter.convert_and_merge(
                [src], recursive=False, merge_filename="context.md"
            )

        assert (out / "context.md").exists()
        assert not (out / "merged.md").exists()
        assert results[0].output_path == out / "context.md"

    def test_default_merge_filename(self, tmp_path):
        """Default filename should be merged.md."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.pdf").touch()

        results_map = {
            "doc.pdf": ConversionResult(
                source_path=src / "doc.pdf",
                success=True,
                markdown="Doc content.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            converter.convert_and_merge([src], recursive=False)

        assert (out / "merged.md").exists()


class TestDryRunMerge:
    def test_dry_run_does_not_write_file(self, tmp_path):
        """Dry run should not create the merged file."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.pdf").touch()

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        results = converter.convert_and_merge([src], recursive=False, dry_run=True)

        assert not (out / "merged.md").exists()
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].markdown == "[dry run]"

    def test_dry_run_shows_merged_output_path(self, tmp_path):
        """Dry run results should show the merged output path."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.pdf").touch()
        (src / "b.pdf").touch()

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        results = converter.convert_and_merge([src], recursive=False, dry_run=True)

        for result in results:
            assert result.output_path == out / "merged.md"


class TestSingleFileMerge:
    def test_single_file_merge(self, tmp_path):
        """Merge mode with a single file should still work."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "only.pdf").touch()

        results_map = {
            "only.pdf": ConversionResult(
                source_path=src / "only.pdf",
                success=True,
                markdown="Only content.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            results = converter.convert_and_merge([src], recursive=False)

        content = (out / "merged.md").read_text(encoding="utf-8")

        # Single file: header + content, no separator
        assert "# only.pdf" in content
        assert "Only content." in content
        assert "---" not in content


class TestMergeEmptyInput:
    def test_merge_with_no_files(self, tmp_path):
        """Merge with no matching files should return empty list."""
        src = tmp_path / "empty"
        src.mkdir()

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        results = converter.convert_and_merge([src], recursive=False)

        assert results == []
        assert not (out / "merged.md").exists()


class TestMergeOutputPath:
    def test_merge_uses_output_dir(self, tmp_path):
        """When output_dir is set, merged file goes there."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.pdf").touch()

        results_map = {
            "doc.pdf": ConversionResult(
                source_path=src / "doc.pdf",
                success=True,
                markdown="Content.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            converter.convert_and_merge([src], recursive=False)

        assert (out / "merged.md").exists()

    def test_merge_uses_cwd_when_no_output_dir(self, tmp_path):
        """When no output_dir is set, merged file goes to cwd."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.pdf").touch()

        results_map = {
            "doc.pdf": ConversionResult(
                source_path=src / "doc.pdf",
                success=True,
                markdown="Content.",
            ),
        }

        converter = FileConverter(output_dir=None)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)), \
             patch("fileconverter.converter.Path.cwd", return_value=tmp_path):
            results = converter.convert_and_merge([src], recursive=False)

        assert (tmp_path / "merged.md").exists()
        assert results[0].output_path == tmp_path / "merged.md"

    def test_no_individual_files_written(self, tmp_path):
        """Merge mode should NOT write individual .md files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "alpha.pdf").touch()
        (src / "beta.pdf").touch()

        results_map = {
            "alpha.pdf": ConversionResult(
                source_path=src / "alpha.pdf",
                success=True,
                markdown="Alpha.",
            ),
            "beta.pdf": ConversionResult(
                source_path=src / "beta.pdf",
                success=True,
                markdown="Beta.",
            ),
        }

        out = tmp_path / "out"
        converter = FileConverter(output_dir=out)

        with patch.object(FileConverter, "convert_file", _make_fake_convert(results_map)):
            converter.convert_and_merge([src], recursive=False)

        # Only merged.md should exist, not individual files
        md_files = list(out.glob("*.md"))
        assert len(md_files) == 1
        assert md_files[0].name == "merged.md"
