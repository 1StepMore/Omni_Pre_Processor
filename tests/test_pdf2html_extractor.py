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


# ---------------------------------------------------------------------------
# OPP#24 — image position tests
# ---------------------------------------------------------------------------

# 1x1 black RGB PNG (generated via struct+zlib)
_MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00'
    b'\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82'
)


def test_pdf2html_image_position_matches_get_image_info(tmp_path: Path):
    """OPP#24: <img> position uses get_image_info() bbox, not text matrix."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "single.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    assert '<img style="position:absolute' in html, f"Missing absolute img: {html[:500]}"
    assert "left:100.0pt" in html, f"Missing left:100.0pt: {html[:500]}"
    assert "top:642.0pt" in html, f"Missing top:642.0pt (842-200): {html[:500]}"
    assert "width:100.0pt" in html
    assert "height:100.0pt" in html


def test_pdf2html_no_images_yields_no_img_tags(tmp_path: Path):
    """OPP#24: PDF without images produces no <img> in skeleton_html."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Text only")
    pdf_path = tmp_path / "no_img.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    assert "src=\"data:" not in html, f"Found base64 src in text-only PDF: {html[:500]}"
    assert "position:absolute" not in html, f"Found absolute img in text-only PDF: {html[:500]}"


def test_pdf2html_multi_image_positions_all_correct(tmp_path: Path):
    """OPP#24: Each image in multi-image PDF has correct bbox."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    page.insert_image(fitz.Rect(300, 400, 450, 500), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "multi.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    img_count = html.count('<img style="position:absolute')
    assert img_count == 2, f"Expected 2 img tags, found {img_count}"

    # Image 1: left=100, top=842-200=642, width=100, height=100
    assert "left:100.0pt" in html
    assert "top:642.0pt" in html
    assert "width:100.0pt" in html

    # Image 2: left=300, top=842-500=342, width=150, height=100
    assert "left:300.0pt" in html
    assert "top:342.0pt" in html
    assert "width:150.0pt" in html
    assert "height:100.0pt" in html


def test_pdf2html_multi_page_images(tmp_path: Path):
    """OPP#24: Images on different pages each have correct positions."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_image(fitz.Rect(50, 50, 150, 150), stream=_MINIMAL_PNG)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_image(fitz.Rect(200, 300, 300, 400), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "multi_page.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    img_count = html.count('<img style="position:absolute')
    assert img_count == 2, f"Expected 2 img tags, got {img_count}"

    # Page 1: left=50, top=842-150=692
    assert "left:50.0pt" in html
    assert "top:692.0pt" in html
    # Page 2: left=200, top=842-400=442
    assert "left:200.0pt" in html
    assert "top:442.0pt" in html


def test_pdf2html_image_with_alpha_channel(tmp_path: Path):
    """OPP#24: RGBA images are handled without error."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "alpha.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)  # Must not raise
    assert result.skeleton_html is not None
    assert '<img style="position:absolute' in (result.skeleton_html or "")


def test_pdf2html_images_still_marked_inline(tmp_path: Path):
    """OPP#22 regression: images still have is_inline_in_md=True after fix."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "regression.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)

    assert len(result.images) >= 1, f"Expected at least 1 image, got {len(result.images)}"
    for img in result.images:
        assert img.is_inline_in_md is True, f"Image {img.path} not inline: {img.is_inline_in_md}"


def test_pdf2html_custom_css_doesnt_break_images(tmp_path: Path):
    """OPP#24: custom CSS still produces correct image positions."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "custom_css.pdf"
    doc.save(str(pdf_path))
    doc.close()

    custom_css = "body { background: lightblue; }"
    result = PDF2HTMLExtractor().extract(pdf_path, css=custom_css)
    html = result.skeleton_html or ""

    assert custom_css in html, "Custom CSS not injected"
    assert "left:100.0pt" in html, "Image position wrong with custom CSS"
    assert "top:642.0pt" in html
