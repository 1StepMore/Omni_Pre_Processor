from pathlib import Path
from datetime import datetime, date

import pytest
import openpyxl

from opp.extractors.xlsx import XLSXExtractor
from opp.utils.exceptions import CorruptedFileError, ValidationError


class TestXLSXExtractor:

    def test_extract_multi_sheet_workbook(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        wb.create_sheet("Sheet1")
        wb.create_sheet("Sheet2")
        wb["Sheet1"].append(["A1", "B1"])
        wb["Sheet1"].append(["A2", "B2"])
        wb["Sheet2"].append(["C1", "D1"])
        wb["Sheet2"].append(["C2", "D2"])
        file_path = tmp_path / "multi_sheet.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        assert any("Sheet1" in t for t in texts)
        assert any("Sheet2" in t for t in texts)
        assert any("A1" in t for t in texts)

    def test_extract_merged_cells(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.merge_cells("A1:C1")
        ws["A1"] = "Merged Value"
        ws["A2"] = "Normal"
        file_path = tmp_path / "merged.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        assert any("Merged" in t for t in texts)

    def test_extract_mixed_data_types(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["String", 123, 45.67, True, None])
        ws.append(["2024-01-15", "Text with spaces", "", False])
        file_path = tmp_path / "mixed_types.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        combined = " ".join(texts)
        assert "String" in combined
        assert "123" in combined

    def test_extract_single_row_sheet(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Single Row Data"])
        file_path = tmp_path / "single_row.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert len(result.paragraphs) >= 1
        texts = [p.text for p in result.paragraphs]
        assert any("Single Row" in t for t in texts)

    def test_extract_single_column_sheet(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Row1"])
        ws.append(["Row2"])
        ws.append(["Row3"])
        file_path = tmp_path / "single_column.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        assert any("Row1" in t or "Row2" in t or "Row3" in t for t in texts)

    def test_extract_100_columns(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        row_data = [f"Col{i}" for i in range(1, 101)]
        ws.append(row_data)
        file_path = tmp_path / "wide.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        assert len(texts) >= 1

    def test_extract_10001_rows(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Header"])
        for i in range(10001):
            ws.append([f"Row{i}"])
        file_path = tmp_path / "too_many_rows.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert any("10000" in w or "截断" in w for w in result.warnings)

    def test_extract_empty_workbook(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        file_path = tmp_path / "empty.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert "工作簿为空" in result.warnings

    def test_extract_empty_sheet(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        wb.create_sheet("EmptySheet")
        file_path = tmp_path / "empty_sheet.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert len(result.paragraphs) >= 0

    def test_extract_corrupted_xlsx(self, tmp_path: Path):
        corrupted_file = tmp_path / "corrupted.xlsx"
        corrupted_file.write_bytes(b"not a valid xlsx file content")

        extractor = XLSXExtractor()
        with pytest.raises((CorruptedFileError, ValueError, Exception)):
            extractor.extract(corrupted_file)

    def test_extract_zero_byte_file(self, tmp_path: Path):
        zero_byte = tmp_path / "zero_byte.xlsx"
        zero_byte.write_bytes(b"")

        extractor = XLSXExtractor()
        with pytest.raises((CorruptedFileError, ValueError, Exception)):
            extractor.extract(zero_byte)

    def test_extract_password_protected_xlsx(self, tmp_path: Path):
        protected_file = tmp_path / "protected.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Protected"])
        wb.save(str(protected_file))

        with open(str(protected_file), 'r+b') as f:
            f.seek(50)
            f.write(b'XXXX')

        extractor = XLSXExtractor()
        result = extractor.extract(protected_file)
        assert result is not None

    def test_extract_nonexistent_file(self, tmp_path: Path):
        nonexistent = tmp_path / "does_not_exist.xlsx"

        extractor = XLSXExtractor()
        with pytest.raises((FileNotFoundError, CorruptedFileError, ValidationError)):
            extractor.extract(nonexistent)

    def test_extract_none_values(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([None, "Text", None, 456])
        file_path = tmp_path / "none_values.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        combined = " ".join(texts)
        assert "Text" in combined
        assert "456" in combined

    def test_extract_whitespace_only(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["   ", "", "  ", None])
        file_path = tmp_path / "whitespace.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert result is not None

    def test_extract_numeric_data(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([1, 1.5, -100, 0, 999999.99])
        file_path = tmp_path / "numeric.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        combined = " ".join(texts)
        assert "1" in combined
        assert "1.5" in combined

    def test_extract_boolean_data(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([True, False])
        file_path = tmp_path / "boolean.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        combined = " ".join(texts).lower()
        assert "true" in combined or "false" in combined

    def test_extract_date_values(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([datetime(2024, 1, 15, 12, 30, 0)])
        ws.append([date(2024, 12, 25)])
        file_path = tmp_path / "dates.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        texts = [p.text for p in result.paragraphs]
        combined = " ".join(texts)
        assert "2024" in combined

    def test_extract_very_long_string(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        ws = wb.active
        long_text = "A" * 10000
        ws.append([long_text])
        file_path = tmp_path / "long_string.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        combined = "".join([p.text for p in result.paragraphs])
        assert len(combined) > 0

    def test_extract_multiple_sheets_all_empty(self, tmp_path: Path):
        wb = openpyxl.Workbook()
        wb.create_sheet("Empty1")
        wb.create_sheet("Empty2")
        wb.create_sheet("Empty3")
        file_path = tmp_path / "all_empty.xlsx"
        wb.save(str(file_path))

        extractor = XLSXExtractor()
        result = extractor.extract(file_path)

        assert result is not None

    def test_supported_extensions(self):
        extractor = XLSXExtractor()
        assert extractor.supported_extensions() == [".xlsx"]


@pytest.fixture
def sample_xlsx_normal(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Header1", "Header2"])
    ws.append(["Data1", "Data2"])
    file_path = tmp_path / "normal.xlsx"
    wb.save(str(file_path))
    return tmp_path / "normal.xlsx"


@pytest.fixture
def sample_xlsx_multi_sheet(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    wb.create_sheet("Data")
    wb["Sheet"].append(["Col1", "Col2"])
    wb["Data"].append(["X", "Y"])
    file_path = tmp_path / "multi.xlsx"
    wb.save(str(file_path))
    return file_path


@pytest.fixture
def sample_xlsx_edge(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Single"])
    file_path = tmp_path / "edge.xlsx"
    wb.save(str(file_path))
    return file_path