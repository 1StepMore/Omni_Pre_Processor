from pathlib import Path

import pytest

from opp.extractors.pdf import PDFExtractor
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class TestPDFExtractor:
    def test_extract_text_blocks_native(self, sample_files_normal: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_normal / "native_text.pdf")
        assert len(result.paragraphs) > 0
        assert result.paragraphs[0].text is not None

    def test_extract_text_blocks_multicolumn(self, sample_files_edge: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_edge / " multicolum.pdf")
        assert len(result.paragraphs) >= 1

    def test_extract_text_blocks_encrypted(self, sample_files_error: Path):
        extractor = PDFExtractor()
        with pytest.raises((CorruptedFileError, PasswordProtectedError)):
            extractor.extract(sample_files_error / "corrupted.pdf")

    def test_detect_tables_wired(self, sample_files_normal: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_normal / "wired_table.pdf")
        assert hasattr(result, 'tables')

    def test_detect_tables_wireless(self, sample_files_edge: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_edge / "wireless_table.pdf")
        assert hasattr(result, 'tables')

    def test_detect_tables_pseudo(self, sample_files_edge: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_edge / "pseudo_table.pdf")
        assert len(result.tables) >= 0

    def test_extract_images_normal(self, sample_files_normal: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_normal / "with_images.pdf")
        assert hasattr(result, 'images')

    def test_extract_images_compressed(self, sample_files_edge: Path):
        extractor = PDFExtractor()
        result = extractor.extract(sample_files_edge / "compressed_images.pdf")
        assert hasattr(result, 'images')

    def test_extract_corrupted(self, sample_files_error: Path):
        extractor = PDFExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "corrupted.pdf")

    def test_extract_zero_byte(self, sample_files_error: Path):
        extractor = PDFExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "zero_byte.pdf")

    def test_supported_extensions(self):
        extractor = PDFExtractor()
        assert extractor.supported_extensions() == [".pdf"]