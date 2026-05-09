from pathlib import Path

import pytest

from opp.extractors.docx import DOCXExtractor
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class TestDOCXExtractor:
    def test_extract_paragraphs_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "normal.docx")
        assert len(result.paragraphs) == 3
        assert result.paragraphs[0].text == "Heading 1"
        assert result.paragraphs[0].level == 1
        assert result.paragraphs[1].style == "Normal"

    def test_extract_paragraphs_empty(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "empty.docx")
        assert len(result.paragraphs) == 0
        assert "文档为空" in result.warnings

    def test_extract_paragraphs_single(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "single_para.docx")
        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].text == "Single Paragraph"

    def test_extract_tables_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_table.docx")
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["Header1", "Header2"]
        assert len(result.tables[0].rows) == 2

    def test_extract_tables_nested(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "nested_table.docx")
        assert len(result.tables) >= 2

    def test_extract_images_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_image.docx")
        assert hasattr(result, 'images')

    def test_extract_images_single(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "single_image.docx")
        assert hasattr(result, 'images')

    def test_extract_corrupted(self, sample_files_error: Path):
        extractor = DOCXExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "corrupted.docx")

    def test_extract_password_protected(self, sample_files_error: Path):
        extractor = DOCXExtractor()
        with pytest.raises((CorruptedFileError, FileNotFoundError)):
            extractor.extract(sample_files_error / "nonexistent.docx")

    def test_supported_extensions(self):
        extractor = DOCXExtractor()
        assert extractor.supported_extensions() == [".docx"]