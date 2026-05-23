"""Tests for PDF TOC extraction via doc.get_toc()."""

from pathlib import Path

import fitz
import pytest

from opp.extractors.pdf import PDFExtractor
from opp.utils.dataclasses import ParagraphData


def create_pdf_with_bookmarks(tmp_path: Path, bookmarks: list) -> Path:
    pdf = fitz.open()
    for i in range(max(b[2] for b in bookmarks) if bookmarks else 1):
        pdf.new_page(width=595, height=842)

    pdf.set_toc(bookmarks)

    pdf.save(str(tmp_path / "toc_test.pdf"))
    pdf.close()
    return tmp_path / "toc_test.pdf"


class TestPDFExtractorTOC:
    """Test TOC extraction using doc.get_toc()."""

    def test_toc_with_bookmarks(self, tmp_path: Path):
        """Given PDF with bookmarks → expect TOC ParagraphData with level=1-6, style='Heading N'."""
        bookmarks = [
            (1, "Chapter 1", 1),
            (2, "Section 1.1", 1),
            (3, "Subsection 1.1.1", 1),
            (4, "Section 1.2", 2),
            (5, "Deep Section", 2),
            (6, "Deepest Section", 2),
        ]
        pdf_path = create_pdf_with_bookmarks(tmp_path, bookmarks)

        extractor = PDFExtractor()
        toc_entries = extractor.extract_toc(pdf_path)

        assert len(toc_entries) == len(bookmarks)
        for i, (level, title, _) in enumerate(bookmarks):
            assert toc_entries[i].text == title
            assert toc_entries[i].level == level
            assert toc_entries[i].style == f"Heading {level}"

    def test_toc_no_bookmarks(self, tmp_path: Path):
        """Given PDF with no bookmarks → expect empty TOC list, no error."""
        pdf = fitz.open()
        pdf.new_page(width=595, height=842)
        pdf.save(str(tmp_path / "no_toc.pdf"))
        pdf.close()

        extractor = PDFExtractor()
        toc_entries = extractor.extract_toc(tmp_path / "no_toc.pdf")

        assert toc_entries == []
        assert isinstance(toc_entries, list)

    def test_toc_2_level_hierarchy(self, tmp_path: Path):
        """Given PDF with 2-level TOC → expect level=1 for top-level, level=2 for nested."""
        bookmarks = [
            (1, "Introduction", 1),
            (2, "Background", 1),
            (1, "Main Content", 2),
            (2, "Part A", 2),
            (2, "Part B", 3),
        ]
        pdf_path = create_pdf_with_bookmarks(tmp_path, bookmarks)

        extractor = PDFExtractor()
        toc_entries = extractor.extract_toc(pdf_path)

        assert len(toc_entries) == 5

        level_1_entries = [e for e in toc_entries if e.level == 1]
        assert len(level_1_entries) == 2
        assert all(e.style == "Heading 1" for e in level_1_entries)

        level_2_entries = [e for e in toc_entries if e.level == 2]
        assert len(level_2_entries) == 3
        assert all(e.style == "Heading 2" for e in level_2_entries)