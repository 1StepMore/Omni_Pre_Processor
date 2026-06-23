"""E2E-81 regression tests.

The bug: when a CSV cell contains a quoted multi-line value
(common in spreadsheet exports), two things broke:

  1. ``opp.extractors.csv.CSVExtractor`` read with
     ``on_bad_lines="skip"`` — a row that pandas mis-parsed (e.g. a
     stray quote) was silently dropped, even when the parse was
     actually fine. Downstream LLM-driven flows rely on every row
     being either correctly parsed or loudly failed.

  2. ``opp.markdown.generator.MarkdownGenerator._escape_table_cell``
     did ``cell.replace('|', '\\|').replace('\\n', ' ')`` which
     collapsed every embedded newline into a single space, so
     multi-line cells became one unreadable blob in the rendered
     markdown table.

The fix:
  1. ``on_bad_lines="warn"`` so mis-parses surface as warnings.
  2. Escape newlines as ``<br>`` (which pandoc renders as a soft
     line break in tables) instead of a single space, and collapse
     any surrounding whitespace.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from opp.extractors.csv import CSVExtractor
from opp.markdown.generator import MarkdownGenerator
from opp.utils.dataclasses import ExtractionResult, TableData


class TestCsvExtractorPreservesMultiline:
    def test_multiline_cell_preserved_after_extraction(self, tmp_path: Path):
        csv_text = (
            'name,description\n'
            'Alice,"She said:\nhello world\n"\n'
            'Bob,"single line"\n'
            'Charlie,"Another\nmulti-line\nfield"\n'
        )
        p = tmp_path / "test.csv"
        p.write_text(csv_text, encoding="utf-8")
        result = CSVExtractor().extract(p)
        assert len(result.tables) == 1
        rows = result.tables[0].rows
        # Row 0 — Alice's cell has the embedded \n.
        assert rows[0][0] == "Alice"
        assert "She said:" in rows[0][1]
        assert "hello world" in rows[0][1]
        assert "\n" in rows[0][1], (
            f"Multi-line cell content must keep its newlines. Got: {rows[0][1]!r}"
        )

    def test_no_rows_silently_dropped(self, tmp_path: Path):
        csv_text = (
            'a,b\n'
            '1,"x"\n'
            '2,"y\nz"\n'  # multi-line cell
            '3,"w"\n'
        )
        p = tmp_path / "test.csv"
        p.write_text(csv_text, encoding="utf-8")
        result = CSVExtractor().extract(p)
        # 3 data rows + 1 header. All must be present.
        assert len(result.tables[0].rows) == 3, (
            f"Expected 3 data rows, got {len(result.tables[0].rows)}"
        )


class TestMarkdownGeneratorPreservesMultiline:
    def test_escape_table_cell_keeps_newline_as_br(self):
        cell = "line one\nline two"
        escaped = MarkdownGenerator()._escape_table_cell(cell)
        assert escaped == "line one<br>line two", (
            f"Multi-line cell should be joined with <br>. Got: {escaped!r}"
        )

    def test_escape_table_cell_collapses_surrounding_whitespace(self):
        cell = "line one  \n  line two"
        escaped = MarkdownGenerator()._escape_table_cell(cell)
        assert escaped == "line one<br>line two", (
            f"Surrounding whitespace around \\n should collapse. Got: {escaped!r}"
        )

    def test_escape_table_cell_escapes_pipe(self):
        cell = "col1|col2"
        escaped = MarkdownGenerator()._escape_table_cell(cell)
        assert escaped == "col1\\|col2", (
            f"Pipe must be escaped to avoid breaking table syntax. "
            f"Got: {escaped!r}"
        )

    def test_escape_table_cell_handles_carriage_return(self):
        cell = "line one\r\nline two"
        escaped = MarkdownGenerator()._escape_table_cell(cell)
        assert "\r" not in escaped
        assert "line one<br>line two" == escaped

    def test_escape_table_cell_no_newline_passthrough(self):
        cell = "just one line"
        escaped = MarkdownGenerator()._escape_table_cell(cell)
        assert escaped == "just one line"

    def test_table_round_trip_preserves_multiline(self, tmp_path: Path):
        """End-to-end: CSV with multi-line cell → markdown table with <br>."""
        csv_text = (
            'name,description\n'
            'Alice,"line one\nline two"\n'
        )
        p = tmp_path / "test.csv"
        p.write_text(csv_text, encoding="utf-8")
        result = CSVExtractor().extract(p)
        md = MarkdownGenerator().generate_tables_md(result.tables)
        # The cell's newline should be in the table as <br>.
        assert "line one<br>line two" in md, (
            f"Multi-line cell must round-trip through markdown. Got:\n{md}"
        )
        # And the table must be valid (no extra row from the \n).
        rows = [ln for ln in md.splitlines() if ln.startswith("|")]
        # 1 header + 1 separator + 1 data = 3.
        assert len(rows) == 3, f"Table has wrong row count: {rows}"
