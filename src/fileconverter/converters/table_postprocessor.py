"""Post-processing for markdown tables extracted from PDFs.

Detects and fixes degenerate tables (e.g., flowcharts misread as tables)
and cleans up normal tables (br tags, generic headers, redundant rows).
"""

import re
from dataclasses import dataclass, field


# --- Thresholds (tuneable) ---
MIN_COLUMNS_FOR_DEGENERATE = 10
DUPLICATION_RATIO_THRESHOLD = 0.5
GENERIC_HEADER_RATIO_THRESHOLD = 0.5
REDUNDANT_ROW_RATIO_THRESHOLD = 0.7

_GENERIC_HEADER_RE = re.compile(r"^Col\d+$", re.IGNORECASE)
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_FORMAT_HINT_RE = re.compile(
    r"^\s*(?:hh:mm|dd/mm|yyyy|mm/dd|n[./]a\.?|start\s*time|end\s*time|-\s*end)\s*$",
    re.IGNORECASE,
)


@dataclass
class ParsedTable:
    """A parsed markdown table."""

    header_cells: list[str]
    data_rows: list[list[str]]
    start_line: int  # inclusive
    end_line: int  # inclusive


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into cells, respecting escaped pipes."""
    stripped = line.strip()
    # Remove leading/trailing pipes
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(stripped):
        if stripped[i] == "\\" and i + 1 < len(stripped) and stripped[i + 1] == "|":
            current.append("\\|")
            i += 2
        elif stripped[i] == "|":
            cells.append("".join(current).strip())
            current = []
            i += 1
        else:
            current.append(stripped[i])
            i += 1
    cells.append("".join(current).strip())
    return cells


def _is_separator_line(line: str) -> bool:
    """Return True if *line* is a markdown table separator row."""
    stripped = line.strip()
    if not stripped:
        return False
    cells = _split_row(stripped)
    if len(cells) < 1:
        return False
    return all(_SEPARATOR_CELL_RE.match(c.strip()) for c in cells if c.strip())


def _is_table_row(line: str) -> bool:
    """Return True if *line* looks like a markdown table row."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1


def find_tables(markdown: str) -> list[ParsedTable]:
    """Find and parse all markdown tables in *markdown*."""
    lines = markdown.split("\n")
    tables: list[ParsedTable] = []
    used: set[int] = set()

    for i, line in enumerate(lines):
        if i in used:
            continue
        if not _is_separator_line(line):
            continue
        # Separator found at line i. Header must be the line before.
        if i == 0 or not _is_table_row(lines[i - 1]):
            continue

        header_cells = _split_row(lines[i - 1])
        sep_cells = _split_row(lines[i])

        # Column count must roughly match
        if abs(len(header_cells) - len(sep_cells)) > 1:
            continue

        # Collect data rows following the separator
        data_rows: list[list[str]] = []
        j = i + 1
        while j < len(lines) and _is_table_row(lines[j]) and not _is_separator_line(lines[j]):
            data_rows.append(_split_row(lines[j]))
            j += 1

        start = i - 1
        end = j - 1  # last line that is part of the table

        for idx in range(start, end + 1):
            used.add(idx)

        tables.append(
            ParsedTable(
                header_cells=header_cells,
                data_rows=data_rows,
                start_line=start,
                end_line=end,
            )
        )

    return tables


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _row_duplication_ratio(cells: list[str]) -> float:
    """Fraction of non-empty cells that are duplicates of another cell in the row."""
    non_empty = [c for c in cells if c.strip()]
    if not non_empty:
        return 0.0
    unique = set(non_empty)
    return 1.0 - len(unique) / len(non_empty)


def _generic_header_ratio(headers: list[str]) -> float:
    """Fraction of non-empty headers matching the ``ColN`` pattern."""
    non_empty = [h for h in headers if h.strip()]
    if not non_empty:
        return 0.0
    generic = sum(1 for h in non_empty if _GENERIC_HEADER_RE.match(h.strip()))
    return generic / len(non_empty)


def is_degenerate(table: ParsedTable) -> bool:
    """Return True if *table* is likely a misdetected diagram."""
    col_count = len(table.header_cells)
    if col_count < MIN_COLUMNS_FOR_DEGENERATE:
        return False

    # Check generic header ratio
    gh_ratio = _generic_header_ratio(table.header_cells)

    # Check average intra-row duplication
    if table.data_rows:
        avg_dup = sum(_row_duplication_ratio(r) for r in table.data_rows) / len(
            table.data_rows
        )
    else:
        avg_dup = 0.0

    return avg_dup >= DUPLICATION_RATIO_THRESHOLD or gh_ratio >= GENERIC_HEADER_RATIO_THRESHOLD


# ---------------------------------------------------------------------------
# Degenerate table restructuring
# ---------------------------------------------------------------------------


def _clean_br(text: str) -> str:
    """Replace ``<br>`` tags with a space and collapse whitespace."""
    cleaned = re.sub(r"<br\s*/?>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _split_on_br(text: str) -> list[str]:
    """Split *text* on ``<br>`` tags and return non-empty fragments."""
    parts = re.split(r"<br\s*/?>", text)
    return [p.strip() for p in parts if p.strip()]


def _strip_bold(text: str) -> str:
    """Remove markdown bold markers."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def restructure_degenerate(table: ParsedTable) -> str:
    """Convert a degenerate table into a structured markdown list."""
    lines: list[str] = []

    # Determine if column 0 is a repeated title
    col0_values = {_strip_bold(_clean_br(r[0])).strip() for r in table.data_rows if r and r[0].strip()}
    title: str | None = None
    if len(col0_values) == 1:
        title = col0_values.pop()

    if title:
        lines.append(f"## {title}")
        lines.append("")

    # Build an ordered mapping of role -> merged content items
    # This merges duplicate rows with the same role name.
    role_items: dict[str, list[str]] = {}
    role_order: list[str] = []

    # If the header row itself has role-like data (e.g., "Change Requestor" in col 1)
    if len(table.header_cells) > 1:
        role_header = _strip_bold(_clean_br(table.header_cells[1])).strip()
        if role_header and not _GENERIC_HEADER_RE.match(role_header):
            content_items = _collect_unique_items(table.header_cells[2:])
            if content_items:
                role_items[role_header] = content_items
                role_order.append(role_header)

    for row in table.data_rows:
        if not row:
            continue

        # Determine role name (column 1, or column 0 if no title)
        role_col = 1 if title and len(row) > 1 else 0
        role = _strip_bold(_clean_br(row[role_col])).strip() if role_col < len(row) else ""

        # Content columns
        content_start = role_col + 1
        content_cells = row[content_start:] if content_start < len(row) else []

        content_items = _collect_unique_items(content_cells)

        if role:
            if role not in role_items:
                role_items[role] = []
                role_order.append(role)
            # Merge items, deduplicating
            existing = set(role_items[role])
            for item in content_items:
                if item not in existing:
                    role_items[role].append(item)
                    existing.add(item)

    # Emit sections in order
    for role in role_order:
        items = _merge_short_fragments(role_items[role])
        lines.append(f"### {role}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def _merge_short_fragments(items: list[str]) -> list[str]:
    """Merge short text fragments that are likely split across PDF cell boundaries.

    Handles both adjacent fragments (e.g., ["YE", "S"] -> ["YES"]) and
    non-adjacent alpha fragments separated by longer content
    (e.g., ["YE", "Consulting and analysis", "S"] -> ["YES", "Consulting and analysis"]).
    """
    if len(items) <= 1:
        return items

    # Threshold: items with this many chars or fewer are considered fragments
    frag_len = 4

    # First pass: merge non-adjacent short alpha fragments separated by
    # longer items.  This fixes cases where pymupdf4llm splits a flowchart
    # label (e.g., "YES") across non-contiguous cells.
    items = _merge_nonadjacent_alpha_fragments(items, frag_len)

    # Second pass: merge remaining adjacent short fragments
    merged: list[str] = []
    i = 0
    while i < len(items):
        item = items[i]
        # If this is a short fragment, try to merge with next item
        if len(item) <= frag_len and i + 1 < len(items):
            next_item = items[i + 1]
            if len(next_item) <= frag_len:
                # Two consecutive short items — join them directly (likely a split word)
                merged.append(item + next_item)
                i += 2
                continue
            else:
                # Short item before a long one — prepend to the next item
                merged.append(item + " " + next_item)
                i += 2
                continue
        elif len(item) <= frag_len and merged:
            # Short item at the end — append to previous
            merged[-1] = merged[-1] + " " + item
            i += 1
            continue
        merged.append(item)
        i += 1

    return merged


def _merge_nonadjacent_alpha_fragments(items: list[str], frag_len: int) -> list[str]:
    """Merge non-adjacent short alphabetic fragments likely split from one word.

    Detects patterns like ["YE", "long content", "S"] where two short
    alpha-only fragments are separated by exactly one longer item, and
    merges them into a single word: ["YES", "long content"].
    """
    if len(items) < 3:
        return items

    result = list(items)
    i = 0
    while i < len(result) - 2:
        a = result[i]
        if len(a) > frag_len or not a.isalpha():
            i += 1
            continue

        mid = result[i + 1]
        b = result[i + 2]
        if len(b) <= frag_len and b.isalpha() and len(mid) > frag_len:
            result[i : i + 3] = [a + b, mid]
            # Skip past the merged word + middle item so we don't
            # accidentally re-merge the new word with later fragments
            i += 2
            continue

        i += 1

    return result


def _collect_unique_items(cells: list[str]) -> list[str]:
    """Collect unique non-empty content from a list of cells.

    Each cell is treated as a single item (``<br>`` replaced with spaces)
    to avoid fragmenting multi-line text into separate bullets.
    Generic ``ColN`` entries are filtered out.
    """
    seen: set[str] = set()
    items: list[str] = []

    for cell in cells:
        if not cell.strip():
            continue
        cleaned = _strip_bold(_clean_br(cell)).strip()
        # Remove strikethrough markers
        cleaned = re.sub(r"~~(.+?)~~", r"\1", cleaned)
        if not cleaned:
            continue
        # Skip generic column names that leaked from the header
        if _GENERIC_HEADER_RE.match(cleaned):
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            items.append(cleaned)

    return items


# ---------------------------------------------------------------------------
# Normal table cleaning
# ---------------------------------------------------------------------------


def _is_redundant_subheader(row: list[str], header: list[str]) -> bool:
    """Return True if *row* is a redundant sub-header of *header*."""
    if not row:
        return False

    matches = 0
    total = max(len(row), 1)

    for i, cell in enumerate(row):
        cleaned = _clean_br(cell).strip()
        if not cleaned:
            matches += 1
            continue
        if _FORMAT_HINT_RE.match(cleaned):
            matches += 1
            continue
        # Check if cell text is a substring of or equal to the corresponding header
        if i < len(header):
            header_clean = _clean_br(header[i]).strip()
            if header_clean and (cleaned in header_clean or header_clean in cleaned):
                matches += 1
                continue

    return matches / total >= REDUNDANT_ROW_RATIO_THRESHOLD


def _infer_column_name(col_index: int, data_rows: list[list[str]]) -> str | None:
    """Try to infer a meaningful name for a generic-header column."""
    values = []
    for row in data_rows:
        if col_index < len(row):
            v = _clean_br(row[col_index]).strip()
            if v:
                values.append(v)

    if not values:
        return None

    # Check if values are sequential integers (likely a "Day" column)
    try:
        ints = [int(v) for v in values]
        if ints == list(range(ints[0], ints[0] + len(ints))):
            return "Day"
    except (ValueError, TypeError):
        pass

    return None


def clean_table(table: ParsedTable) -> str:
    """Clean a normal table and return properly formatted markdown."""
    header = [_clean_br(h) for h in table.header_cells]
    rows = [[_clean_br(c) for c in row] for row in table.data_rows]

    # Fix generic headers
    for i, h in enumerate(header):
        if _GENERIC_HEADER_RE.match(h.strip()):
            inferred = _infer_column_name(i, table.data_rows)
            if inferred:
                header[i] = inferred

    # Remove redundant sub-header row (usually the first data row)
    if rows and _is_redundant_subheader(rows[0], header):
        rows = rows[1:]

    # Detect and remove fully empty columns with generic headers
    col_count = len(header)
    keep_cols: list[int] = []
    for ci in range(col_count):
        is_empty = all(
            (ci >= len(r) or not r[ci].strip()) for r in rows
        )
        is_generic = _GENERIC_HEADER_RE.match(header[ci].strip()) if ci < len(header) else False
        if is_empty and is_generic:
            continue
        keep_cols.append(ci)

    if keep_cols and len(keep_cols) < col_count:
        header = [header[ci] for ci in keep_cols if ci < len(header)]
        rows = [[r[ci] if ci < len(r) else "" for ci in keep_cols] for r in rows]

    return _rebuild_table(header, rows)


def _rebuild_table(header: list[str], rows: list[list[str]]) -> str:
    """Rebuild a markdown table string from header and data rows."""
    if not header:
        return ""

    col_count = len(header)

    # Normalise row lengths
    normalised_rows = []
    for r in rows:
        if len(r) < col_count:
            normalised_rows.append(r + [""] * (col_count - len(r)))
        else:
            normalised_rows.append(r[:col_count])

    # Compute column widths
    widths = [max(3, len(h)) for h in header]
    for r in normalised_rows:
        for ci, cell in enumerate(r):
            if ci < col_count:
                widths[ci] = max(widths[ci], len(cell))

    def _fmt_row(cells: list[str]) -> str:
        parts = []
        for ci, cell in enumerate(cells):
            w = widths[ci] if ci < len(widths) else 3
            parts.append(f" {cell:<{w}} ")
        return "|" + "|".join(parts) + "|"

    lines = [
        _fmt_row(header),
        "|" + "|".join("-" * (w + 2) for w in widths) + "|",
    ]
    for r in normalised_rows:
        lines.append(_fmt_row(r))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def postprocess_tables(markdown: str) -> str:
    """Find, analyse, and clean or restructure all tables in *markdown*."""
    tables = find_tables(markdown)
    if not tables:
        return markdown

    lines = markdown.split("\n")

    # Process in reverse order so that line indices stay valid
    for table in reversed(tables):
        if is_degenerate(table):
            replacement = restructure_degenerate(table)
        else:
            replacement = clean_table(table)

        replacement_lines = replacement.split("\n")
        lines[table.start_line : table.end_line + 1] = replacement_lines

    return "\n".join(lines)
