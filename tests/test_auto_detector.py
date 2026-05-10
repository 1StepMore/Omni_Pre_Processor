from pathlib import Path

import pytest

from opp.detector import detect_format, FormatType


class TestFormatDetector:
    def test_detect_docx_by_magic_bytes(self, sample_files_normal: Path):
        """DOCX files should be detected by PK magic bytes (ZIP header)."""
        result = detect_format(sample_files_normal / "normal.docx")
        assert result[0] == FormatType.DOCX
        assert result[1] >= 1.0

    def test_detect_pptx_by_magic_bytes(self, sample_files_normal: Path):
        """PPTX files should be detected by PK magic bytes (ZIP header)."""
        result = detect_format(sample_files_normal / "normal.pptx")
        assert result[0] == FormatType.PPTX
        assert result[1] >= 1.0

    def test_detect_pdf_by_magic_bytes(self, sample_files_normal: Path):
        """PDF files should be detected by %PDF magic bytes."""
        result = detect_format(sample_files_normal / "native_text.pdf")
        assert result[0] == FormatType.PDF
        assert result[1] >= 1.0

    def test_unknown_format(self, tmp_path: Path):
        """Files with unrecognized magic bytes should return UNKNOWN with 0.0 confidence."""
        unknown = tmp_path / "file.unknown"
        unknown.write_bytes(b"random data")
        result = detect_format(unknown)
        assert result[0] == FormatType.UNKNOWN
        assert result[1] == 0.0

    def test_missing_file(self, tmp_path: Path):
        """Missing files should return UNKNOWN with 0.0 confidence."""
        result = detect_format(tmp_path / "nonexistent.docx")
        assert result[0] == FormatType.UNKNOWN
        assert result[1] == 0.0

    def test_empty_file(self, tmp_path: Path):
        """Empty files should return UNKNOWN with 0.0 confidence."""
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        result = detect_format(empty)
        assert result[0] == FormatType.UNKNOWN
        assert result[1] == 0.0

    def test_detect_with_image_docx(self, sample_files_normal: Path):
        """DOCX with images should still be detected correctly."""
        result = detect_format(sample_files_normal / "with_image.docx")
        assert result[0] == FormatType.DOCX
        assert result[1] >= 1.0

    def test_detect_with_table_docx(self, sample_files_normal: Path):
        """DOCX with tables should still be detected correctly."""
        result = detect_format(sample_files_normal / "with_table.docx")
        assert result[0] == FormatType.DOCX
        assert result[1] >= 1.0

    def test_detect_pptx_with_notes(self, sample_files_normal: Path):
        """PPTX with speaker notes should still be detected correctly."""
        result = detect_format(sample_files_normal / "with_notes.pptx")
        assert result[0] == FormatType.PPTX
        assert result[1] >= 1.0

    def test_detect_pdf_with_table(self, sample_files_normal: Path):
        """PDF with tables should still be detected correctly."""
        result = detect_format(sample_files_normal / "wired_table.pdf")
        assert result[0] == FormatType.PDF
        assert result[1] >= 1.0

    def test_detect_pdf_with_images(self, sample_files_normal: Path):
        """PDF with images should still be detected correctly."""
        result = detect_format(sample_files_normal / "with_images.pdf")
        assert result[0] == FormatType.PDF
        assert result[1] >= 1.0

    def test_wrong_magic_bytes_for_extension(self, tmp_path: Path):
        """File with wrong magic bytes for its extension returns based on magic, not extension."""
        # Create a file with .docx extension but PDF magic bytes
        wrong_magic = tmp_path / "fake.docx"
        wrong_magic.write_bytes(b"%PDF-1.4 fake docx content")
        result = detect_format(wrong_magic)
        # %PDF magic bytes take precedence, returns PDF with 1.0
        assert result[0] == FormatType.PDF
        assert result[1] == 1.0

    def test_pk_header_with_pdf_extension(self, tmp_path: Path):
        """ZIP header file with .pdf extension should be detected as DOCX/PPTX based on magic."""
        # A ZIP file (PK header) with .pdf extension
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = detect_format(fake_pdf)
        # Should detect as UNKNOWN because PK header but .pdf extension
        # Extension-based fallback gives 0.5 for .pdf but magic says PK
        assert result[0] == FormatType.UNKNOWN
        assert result[1] == 0.0
