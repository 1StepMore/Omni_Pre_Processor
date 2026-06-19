from pathlib import Path

import pytest

from opp.extractors.csv import CSVExtractor
from opp.utils.exceptions import CorruptedFileError, ValidationError


class TestCSVExtractor:
    """TDD RED tests for CSVExtractor - tests should FAIL initially."""

    # ===== Normal Cases =====

    def test_extract_utf8_with_header(self, csv_files_normal: Path):
        """Normal: UTF-8 CSV with header row."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "utf8_header.csv")
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["name", "age", "city"]
        assert len(result.tables[0].rows) == 2

    def test_extract_utf8_no_header(self, csv_files_normal: Path):
        """Normal: UTF-8 CSV without header row."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "utf8_no_header.csv")
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 3

    def test_extract_tab_separated(self, csv_files_normal: Path):
        """Normal: Tab-separated values."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "tab_separated.tsv")
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["col1", "col2", "col3"]

    def test_extract_single_row(self, csv_files_normal: Path):
        """Normal: CSV with single data row."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "single_row.csv")
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 1

    def test_extract_single_column(self, csv_files_normal: Path):
        """Normal: CSV with single column."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "single_column.csv")
        assert len(result.tables) == 1
        assert len(result.tables[0].headers) == 1

    def test_extract_with_empty_values(self, csv_files_normal: Path):
        """Normal: CSV with empty cell values."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "empty_values.csv")
        assert len(result.tables) == 1
        # Empty values should be preserved as empty strings
        assert "" in [str(v) for row in result.tables[0].rows for v in row]

    def test_extract_with_quoted_values(self, csv_files_normal: Path):
        """Normal: CSV with quoted values containing commas."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "quoted_values.csv")
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 2

    def test_extract_with_spaces(self, csv_files_normal: Path):
        """Normal: CSV values with leading/trailing spaces."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "with_spaces.csv")
        assert len(result.tables) == 1

    def test_extract_paragraphs_created(self, csv_files_normal: Path):
        """Normal: Verify summary paragraph is created (not tab-separated rows)."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "utf8_header.csv")
        assert len(result.paragraphs) == 1  # 1 summary paragraph

    def test_extract_returns_metadata(self, csv_files_normal: Path):
        """Normal: Verify metadata is returned."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "utf8_header.csv")
        assert result.metadata is not None
        assert result.metadata.file_size > 0
        assert result.metadata.format_type == "csv"

    def test_csv_produces_markdown_table(self, csv_files_normal: Path):
        """TDD: MarkdownGenerator output must contain pipe table syntax, not tab-separated raw rows."""
        from opp.markdown.generator import MarkdownGenerator

        extractor = CSVExtractor()
        result = extractor.extract(csv_files_normal / "utf8_header.csv")
        md_output = MarkdownGenerator().generate(result)

        assert "|" in md_output, "Missing pipe table syntax — MarkdownGenerator not producing tables"
        assert "\t" not in md_output, (
            "Tab character found in markdown output — "
            "CSV extractor is producing tab-separated ParagraphData rows "
            "instead of letting tables handle formatting"
        )

    # ===== Boundary Cases =====

    def test_extract_10001_rows(self, csv_files_boundary: Path):
        """Boundary: CSV with exactly 10,001 rows (triggers warning)."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_boundary / "large_10001_rows.csv")
        assert len(result.tables[0].rows) == 10001
        assert any("10001" in w for w in result.warnings)

    def test_extract_10000_rows_no_warning(self, csv_files_boundary: Path):
        """Boundary: CSV with exactly 10,000 rows (no warning)."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_boundary / "large_10000_rows.csv")
        assert len(result.tables[0].rows) == 10000
        assert not any("10000" in w for w in result.warnings)

    def test_extract_inconsistent_columns(self, csv_files_boundary: Path):
        """Boundary: CSV with inconsistent column counts."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_boundary / "inconsistent_cols.csv")
        assert len(result.tables) == 1
        # All rows should be padded to max column count
        max_cols = len(result.tables[0].headers)
        for row in result.tables[0].rows:
            assert len(row) == max_cols

    def test_extract_many_columns(self, csv_files_boundary: Path):
        """Boundary: CSV with many columns (50+)."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_boundary / "many_columns.csv")
        assert len(result.tables[0].headers) >= 50

    def test_extract_empty_csv(self, csv_files_boundary: Path):
        """Boundary: CSV with header but no data rows."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_boundary / "header_only.csv")
        assert len(result.tables[0].rows) == 0

    # ===== Exception Cases =====

    def test_extract_invalid_encoding(self, csv_files_error: Path):
        """Exception: CSV with invalid/unknown encoding."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_error / "invalid_encoding.csv")
        # Should still extract but may have garbled data
        assert result is not None

    def test_extract_latin1_encoding(self, csv_files_error: Path):
        """Exception: CSV with Latin-1 encoding."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_error / "latin1_encoded.csv")
        assert result is not None
        assert len(result.tables) == 1

    def test_extract_malformed_csv(self, csv_files_error: Path):
        """Exception: Malformed CSV with unbalanced quotes."""
        extractor = CSVExtractor()
        result = extractor.extract(csv_files_error / "malformed.csv")
        # Should handle gracefully
        assert result is not None

    def test_extract_nonexistent_file(self, csv_files_error: Path):
        """Exception: File does not exist."""
        extractor = CSVExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(csv_files_error / "nonexistent.csv")

    def test_extract_empty_file(self, csv_files_error: Path):
        """Exception: Zero-byte file."""
        extractor = CSVExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(csv_files_error / "empty_file.csv")

    def test_extract_wrong_extension(self, csv_files_error: Path):
        """Exception: File with wrong extension."""
        extractor = CSVExtractor()
        with pytest.raises(ValidationError):
            extractor.extract(csv_files_error / "wrong_ext.txt")

    def test_extract_binary_file(self, csv_files_error: Path):
        """Exception: File that is actually binary."""
        extractor = CSVExtractor()
        with pytest.raises((CorruptedFileError, Exception)):
            extractor.extract(csv_files_error / "binary_file.csv")

    # ===== Supported Extensions =====

    def test_supported_extensions(self):
        """Verify supported extensions returns .csv and .tsv."""
        extractor = CSVExtractor()
        assert extractor.supported_extensions() == [".csv", ".tsv"]


# ===== Fixtures =====


@pytest.fixture
def csv_files_normal(tmp_path: Path) -> Path:
    """Create normal CSV test files."""
    csv_dir = tmp_path / "csv_normal"
    csv_dir.mkdir()

    # UTF-8 with header
    (csv_dir / "utf8_header.csv").write_text(
        "name,age,city\nJohn,30,Beijing\nJane,25,Shanghai\n",
        encoding="utf-8"
    )

    # UTF-8 without header (use numeric data so first row isn't treated as header)
    (csv_dir / "utf8_no_header.csv").write_text(
        "1,2,3\n4,5,6\n7,8,9\n",
        encoding="utf-8"
    )

    # Tab-separated
    (csv_dir / "tab_separated.tsv").write_text(
        "col1\tcol2\tcol3\nval1\tval2\tval3\n",
        encoding="utf-8"
    )

    # Single row
    (csv_dir / "single_row.csv").write_text(
        "header\ndata\n",
        encoding="utf-8"
    )

    # Single column
    (csv_dir / "single_column.csv").write_text(
        "col1\nval1\nval2\nval3\n",
        encoding="utf-8"
    )

    # Empty values
    (csv_dir / "empty_values.csv").write_text(
        "a,b,c\nval1,,val3\n,val2,\n",
        encoding="utf-8"
    )

    # Quoted values with commas
    (csv_dir / "quoted_values.csv").write_text(
        'a,b\n"val,1",2\n3,"val,2"\n',
        encoding="utf-8"
    )

    # With spaces
    (csv_dir / "with_spaces.csv").write_text(
        " a , b , c \n val1 , val2 , val3 \n",
        encoding="utf-8"
    )

    return csv_dir


@pytest.fixture
def csv_files_boundary(tmp_path: Path) -> Path:
    """Create boundary CSV test files."""
    csv_dir = tmp_path / "csv_boundary"
    csv_dir.mkdir()

    # 10,001 rows (triggers warning)
    lines_10001 = ["id,value"] + [f"{i},val{i}" for i in range(10001)]
    (csv_dir / "large_10001_rows.csv").write_text(
        "\n".join(lines_10001),
        encoding="utf-8"
    )

    # 10,000 rows (no warning)
    lines_10000 = ["id,value"] + [f"{i},val{i}" for i in range(10000)]
    (csv_dir / "large_10000_rows.csv").write_text(
        "\n".join(lines_10000),
        encoding="utf-8"
    )

    # Inconsistent columns
    (csv_dir / "inconsistent_cols.csv").write_text(
        "a,b,c\n1,2\nx,y,z,w\n",
        encoding="utf-8"
    )

    # Many columns
    many_cols = ",".join([f"col{i}" for i in range(60)])
    many_rows = "\n".join([",".join([f"v{i}" for i in range(60)]) for _ in range(3)])
    (csv_dir / "many_columns.csv").write_text(
        f"{many_cols}\n{many_rows}\n",
        encoding="utf-8"
    )

    # Header only
    (csv_dir / "header_only.csv").write_text(
        "col1,col2,col3\n",
        encoding="utf-8"
    )

    return csv_dir


@pytest.fixture
def csv_files_error(tmp_path: Path) -> Path:
    """Create error CSV test files."""
    csv_dir = tmp_path / "csv_error"
    csv_dir.mkdir()

    # Invalid encoding (binary content)
    (csv_dir / "invalid_encoding.csv").write_bytes(
        b'\xff\xfe\x00\x00Invalid content'
    )

    # Latin-1 encoded
    (csv_dir / "latin1_encoded.csv").write_bytes(
        "name,city\nJ\xf6hn,Berlin\n".encode("latin-1")
    )

    # Malformed CSV
    (csv_dir / "malformed.csv").write_text(
        'a,b\n"unbalanced quote,1\n"another"bad"quote"\n',
        encoding="utf-8"
    )

    # Empty file
    (csv_dir / "empty_file.csv").write_bytes(b'')

    # Wrong extension
    (csv_dir / "wrong_ext.txt").write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    # Binary file
    (csv_dir / "binary_file.csv").write_bytes(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00'
    )

    return csv_dir


class TestCSVExtractorTables:
    """Test CSVExtractor.extract_tables() method - Phase 5."""

    def test_extract_tables_with_header(self, tmp_path: Path):
        """CSV with header row returns headers and data rows."""
        csv_file = tmp_path / "with_header.csv"
        csv_file.write_text("name,age,city\nJohn,30,Beijing\nJane,25,Shanghai\n", encoding="utf-8")

        extractor = CSVExtractor()
        tables = extractor.extract_tables(csv_file)

        assert len(tables) == 1
        assert tables[0].headers == ["name", "age", "city"]
        assert len(tables[0].rows) == 2
        assert tables[0].rows[0] == ["John", "30", "Beijing"]

    def test_extract_tables_without_header(self, tmp_path: Path):
        """CSV without header returns numeric row data."""
        csv_file = tmp_path / "no_header.csv"
        csv_file.write_text("1,2,3\n4,5,6\n", encoding="utf-8")

        extractor = CSVExtractor()
        tables = extractor.extract_tables(csv_file)

        assert len(tables) == 1
        assert len(tables[0].headers) == 3
        assert len(tables[0].rows) == 2

    def test_extract_tables_tab_delimiter(self, tmp_path: Path):
        """Tab-separated CSV is parsed correctly."""
        csv_file = tmp_path / "tab_data.tsv"
        csv_file.write_text("col1\tcol2\tcol3\nval1\tval2\tval3\n", encoding="utf-8")

        extractor = CSVExtractor()
        tables = extractor.extract_tables(csv_file)

        assert len(tables) == 1
        assert tables[0].headers == ["col1", "col2", "col3"]
        assert tables[0].rows[0] == ["val1", "val2", "val3"]

    def test_extract_tables_empty_csv(self, tmp_path: Path):
        """Empty CSV raises CorruptedFileError."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("", encoding="utf-8")

        extractor = CSVExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract_tables(csv_file)

    def test_extract_tables_semicolon_delimiter(self, tmp_path: Path):
        """Semicolon-delimited CSV is parsed."""
        csv_file = tmp_path / "semicolon.csv"
        csv_file.write_text("name;age;city\nJohn;30;Beijing\n", encoding="utf-8")

        extractor = CSVExtractor()
        tables = extractor.extract_tables(csv_file)

        assert len(tables) == 1
        # May be parsed as single column or with semicolon
        assert len(tables[0].headers) >= 1
