"""Tests for the table post-processor module."""

import pytest

from fileconverter.converters.table_postprocessor import (
    ParsedTable,
    _collect_unique_items,
    _is_redundant_subheader,
    _rebuild_table,
    _row_duplication_ratio,
    _split_row,
    clean_table,
    find_tables,
    is_degenerate,
    postprocess_tables,
    restructure_degenerate,
)


# ---- Parsing tests ----


class TestSplitRow:
    def test_simple_row(self):
        assert _split_row("| A | B | C |") == ["A", "B", "C"]

    def test_no_outer_pipes(self):
        assert _split_row("A | B | C") == ["A", "B", "C"]

    def test_escaped_pipe(self):
        assert _split_row("| A \\| B | C |") == ["A \\| B", "C"]

    def test_empty_cells(self):
        assert _split_row("| | B | |") == ["", "B", ""]

    def test_br_tags_preserved(self):
        cells = _split_row("| Hello<br>World | B |")
        assert cells[0] == "Hello<br>World"


class TestFindTables:
    def test_simple_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        tables = find_tables(md)
        assert len(tables) == 1
        t = tables[0]
        assert t.header_cells == ["A", "B"]
        assert t.data_rows == [["1", "2"], ["3", "4"]]
        assert t.start_line == 0
        assert t.end_line == 3

    def test_no_tables(self):
        assert find_tables("Just some text.\nNo tables here.") == []

    def test_table_with_surrounding_text(self):
        md = "Before\n\n| H1 | H2 |\n|---|---|\n| D1 | D2 |\n\nAfter"
        tables = find_tables(md)
        assert len(tables) == 1
        assert tables[0].start_line == 2
        assert tables[0].end_line == 4

    def test_multiple_tables(self):
        md = (
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
            "\nSome text\n\n"
            "| X | Y |\n|---|---|\n| 3 | 4 |"
        )
        tables = find_tables(md)
        assert len(tables) == 2

    def test_header_only_table(self):
        md = "| A | B |\n|---|---|"
        tables = find_tables(md)
        assert len(tables) == 1
        assert tables[0].data_rows == []

    def test_table_with_br_in_cells(self):
        md = "| H1<br>H2 | H3 |\n|---|---|\n| val<br>ue | x |"
        tables = find_tables(md)
        assert len(tables) == 1
        assert tables[0].header_cells[0] == "H1<br>H2"
        assert tables[0].data_rows[0][0] == "val<br>ue"


# ---- Analysis tests ----


class TestRowDuplicationRatio:
    def test_no_duplicates(self):
        assert _row_duplication_ratio(["A", "B", "C"]) == 0.0

    def test_all_duplicates(self):
        ratio = _row_duplication_ratio(["X", "X", "X", "X"])
        assert ratio == pytest.approx(0.75)

    def test_empty_cells_ignored(self):
        assert _row_duplication_ratio(["", "", ""]) == 0.0

    def test_mixed(self):
        # 4 non-empty, 2 unique -> ratio = 1 - 2/4 = 0.5
        ratio = _row_duplication_ratio(["A", "B", "A", "B"])
        assert ratio == pytest.approx(0.5)


class TestIsDegenerate:
    def test_eurosur_like_table(self):
        """21-column table with massive duplication -> degenerate."""
        header = ["Title", "Role"] + [f"Col{i}" for i in range(3, 22)]
        dup_text = "Same content<br>repeated everywhere"
        row1 = ["Title", "Role A"] + [dup_text] * 19
        row2 = ["Title", "Role B"] + [dup_text] * 19
        table = ParsedTable(header_cells=header, data_rows=[row1, row2],
                            start_line=0, end_line=3)
        assert is_degenerate(table) is True

    def test_timesheet_like_table(self):
        """8-column table with no duplication -> not degenerate."""
        header = ["Day", "Sig", "1st In", "1st Out", "2nd In", "2nd Out", "Total", "Shift"]
        row = ["1", "", "", "", "", "", "", "n.a."]
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)
        assert is_degenerate(table) is False

    def test_small_table_not_degenerate(self):
        """Even with duplication, a small table is not flagged."""
        header = ["A", "B", "C"]
        row = ["X", "X", "X"]
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)
        assert is_degenerate(table) is False

    def test_wide_table_no_duplication(self):
        """10+ columns but all unique content -> not degenerate."""
        header = [f"H{i}" for i in range(12)]
        row = [f"val{i}" for i in range(12)]
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)
        assert is_degenerate(table) is False

    def test_generic_headers_trigger_degenerate(self):
        """Many generic ColN headers on a wide table -> degenerate."""
        header = ["Title", "Name"] + [f"Col{i}" for i in range(3, 15)]
        row = ["T", "N"] + ["unique" + str(i) for i in range(12)]
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)
        assert is_degenerate(table) is True


# ---- Degenerate restructuring tests ----


class TestRestructureDegenerate:
    def test_basic_restructuring(self):
        header = ["Title", "Role", "Col3", "Col4", "Col5"]
        row1 = ["**My Title**", "**Role A**", "Action 1<br>Action 2", "Action 1<br>Action 2", ""]
        row2 = ["**My Title**", "**Role B**", "Task X", "Task Y", "Task X"]
        table = ParsedTable(header_cells=header, data_rows=[row1, row2],
                            start_line=0, end_line=3)

        result = restructure_degenerate(table)
        assert "## My Title" in result
        assert "### Role A" in result
        assert "### Role B" in result
        assert "- Action 1 Action 2" in result
        assert "- Task X" in result
        assert "- Task Y" in result

    def test_deduplication(self):
        header = ["T", "R"] + [f"Col{i}" for i in range(10)]
        row = ["**T**", "**R**"] + ["Same text"] * 10
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)

        result = restructure_degenerate(table)
        # "Same text" should appear only once as a bullet
        assert result.count("- Same text") == 1

    def test_br_joined_as_single_item(self):
        header = ["T", "R", "Col3"]
        row = ["**T**", "**R**", "Step 1<br>Step 2<br>Step 3"]
        table = ParsedTable(header_cells=header, data_rows=[row],
                            start_line=0, end_line=2)

        result = restructure_degenerate(table)
        assert "- Step 1 Step 2 Step 3" in result


# ---- Normal table cleaning tests ----


class TestCollectUniqueItems:
    def test_dedup(self):
        items = _collect_unique_items(["A", "B", "A", "C"])
        assert items == ["A", "B", "C"]

    def test_empty_cells_skipped(self):
        items = _collect_unique_items(["", "A", ""])
        assert items == ["A"]

    def test_br_joined_with_space(self):
        items = _collect_unique_items(["X<br>Y"])
        assert items == ["X Y"]

    def test_generic_col_filtered(self):
        items = _collect_unique_items(["Col3", "Real content", "Col4"])
        assert items == ["Real content"]


class TestIsRedundantSubheader:
    def test_timesheet_subheader(self):
        header = ["Day", "Signature of Consultant", "1st enter time"]
        row = ["", "Signature of Consultant", "hh:mm"]
        assert _is_redundant_subheader(row, header) is True

    def test_data_row_not_redundant(self):
        header = ["Day", "Name", "Score"]
        row = ["1", "Alice", "95"]
        assert _is_redundant_subheader(row, header) is False

    def test_empty_row_is_redundant(self):
        header = ["A", "B", "C"]
        row = ["", "", ""]
        assert _is_redundant_subheader(row, header) is True


class TestCleanTable:
    def test_br_replaced_with_space(self):
        table = ParsedTable(
            header_cells=["Signature of<br>Consultant", "1st<br>enter<br>time"],
            data_rows=[["Alice", "09:00"]],
            start_line=0, end_line=2,
        )
        result = clean_table(table)
        assert "Signature of Consultant" in result
        assert "1st enter time" in result
        assert "<br>" not in result

    def test_generic_header_renamed(self):
        table = ParsedTable(
            header_cells=["Col1", "Name"],
            data_rows=[["1", "A"], ["2", "B"], ["3", "C"]],
            start_line=0, end_line=4,
        )
        result = clean_table(table)
        assert "Day" in result
        assert "Col1" not in result

    def test_redundant_subheader_removed(self):
        table = ParsedTable(
            header_cells=["Day", "Time"],
            data_rows=[["", "hh:mm"], ["1", "09:00"]],
            start_line=0, end_line=3,
        )
        result = clean_table(table)
        assert "hh:mm" not in result
        assert "09:00" in result

    def test_empty_generic_columns_removed(self):
        table = ParsedTable(
            header_cells=["Name", "Col2"],
            data_rows=[["Alice", ""], ["Bob", ""]],
            start_line=0, end_line=3,
        )
        result = clean_table(table)
        assert "Col2" not in result
        assert "Alice" in result


# ---- Integration tests ----


class TestPostprocessTables:
    def test_no_tables_passthrough(self):
        md = "Hello world\n\nSome text."
        assert postprocess_tables(md) == md

    def test_normal_table_cleaned(self):
        md = "Before\n\n| H<br>1 | H2 |\n|---|---|\n| A | B |\n\nAfter"
        result = postprocess_tables(md)
        assert "<br>" not in result
        assert "H 1" in result
        assert "Before" in result
        assert "After" in result

    def test_degenerate_table_restructured(self):
        header = "| Title | Role |" + "".join(f" Col{i} |" for i in range(3, 15))
        sep = "|---|---|" + "---|" * 12
        dup_text = "Same"
        row = f"| **T** | **R** |" + "".join(f" {dup_text} |" for _ in range(12))

        md = f"Before\n\n{header}\n{sep}\n{row}\n\nAfter"
        result = postprocess_tables(md)
        # Should not be a markdown table anymore
        assert "---|" not in result
        assert "### R" in result
        assert "Before" in result
        assert "After" in result

    def test_mixed_tables(self):
        # One normal table, some text, one degenerate table
        normal = "| A | B |\n|---|---|\n| 1 | 2 |"
        header_d = "| T | R |" + "".join(f" Col{i} |" for i in range(3, 15))
        sep_d = "|---|---|" + "---|" * 12
        row_d = "| **T** | **R** |" + "".join(" Same |" for _ in range(12))
        degen = f"{header_d}\n{sep_d}\n{row_d}"

        md = f"{normal}\n\nMiddle\n\n{degen}"
        result = postprocess_tables(md)
        # Normal table should still be a table
        assert "| A" in result
        # Degenerate should be restructured
        assert "### R" in result

    def test_rebuild_table_alignment(self):
        header = ["Name", "Score"]
        rows = [["Alice", "100"], ["Bob", "95"]]
        result = _rebuild_table(header, rows)
        lines = result.split("\n")
        assert len(lines) == 4  # header, separator, 2 data rows
        assert lines[0].startswith("|")
        assert "---" in lines[1]
