"""Tests for OPP#20: OPPPipeline uses PDF2HTMLExtractor for PDF input."""
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
    page.insert_text((72, 72), "Hello PDF")
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_pipeline_uses_pdf2html_for_pdf(tmp_path: Path):
    """OPP#20: OPPPipeline.process_file for PDF input returns format_type=HTML."""
    from opp.pipeline import OPPPipeline
    from opp.detector import FormatType

    pdf = _make_simple_pdf(tmp_path)
    p = OPPPipeline(resource_storage_dir=tmp_path)
    result = p.process_file(pdf)
    assert result.format_type == FormatType.HTML, f"Expected HTML, got {result.format_type}"
    assert result.extraction_result is not None
    assert result.extraction_result.skeleton_html is not None
    assert "<head>" in result.extraction_result.skeleton_html
