"""Tests for PDF2HTMLExtractor (PDF→HTML via PyMuPDF)."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_simple_pdf(tmp_path: Path) -> Path:
    """Create a minimal PDF with text for testing."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF (fitz) not installed")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF2HTML")
    page.insert_text((72, 102), "Second paragraph")
    pdf_path = tmp_path / "simple.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_pdf2html_extracts_text(tmp_path: Path):
    """PDF with text -> ExtractionResult with paragraphs and skeleton_html."""
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    pdf_path = _make_simple_pdf(tmp_path)
    extractor = PDF2HTMLExtractor()
    result = extractor.extract(pdf_path)

    assert result.paragraphs, "Expected at least one paragraph"
    assert result.skeleton_html is not None
    assert result.metadata is not None
    assert result.metadata.format_type == "html"


def test_pdf2html_raises_on_missing_file(tmp_path: Path):
    """extract() raises FileNotFoundError for non-existent PDF."""
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    extractor = PDF2HTMLExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract(tmp_path / "nonexistent.pdf")


def test_pdf2html_supported_extensions():
    """supported_extensions() includes .pdf."""
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    extractor = PDF2HTMLExtractor()
    assert ".pdf" in extractor.supported_extensions()


def test_skeleton_html_has_head_and_page_break(tmp_path: Path):
    """OPP#21: skeleton HTML has <head>, <meta charset>, page-break CSS."""
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    pdf_path = _make_simple_pdf(tmp_path)
    extractor = PDF2HTMLExtractor()
    result = extractor.extract(pdf_path)
    html = result.skeleton_html or ""
    assert "<!DOCTYPE html>" in html
    assert "<head>" in html and "</head>" in html
    assert '<meta charset="UTF-8"' in html
    assert "page-break-after" in html
    assert "last-of-type" in html


def test_pdf2html_custom_css(tmp_path: Path):
    """OPP#21: custom CSS parameter is injected into <style>."""
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    pdf_path = _make_simple_pdf(tmp_path)
    extractor = PDF2HTMLExtractor()
    custom = "body { background: red; }"
    result = extractor.extract(pdf_path, css=custom)
    assert custom in (result.skeleton_html or "")
