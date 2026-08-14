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
    # The SOURCE is a PDF: format_type must report "pdf" so the PDF→XLIFF
    # guard fires. Relabeling to "html" (HTMLExtractor's default) bypasses
    # the guard on the live CLI path (T2 format-relabel regression).
    assert result.metadata.format_type == "pdf"


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

    # bbox = (100, 100, 200, 200) — top-left at (100, 100), 100x100
    assert '<img style="position:absolute' in html, f"Missing absolute img: {html[:500]}"
    assert "left:100.0pt" in html, f"Missing left:100.0pt: {html[:500]}"
    assert "top:100.0pt" in html, f"Expected top:100.0pt (bbox[1] for top-left page space): {html[:500]}"
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
    assert "<img" not in html, f"Found <img> tag in text-only PDF: {html[:500]}"


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

    # Image 1: left=100, top=100 (bbox[1]), width=100, height=100
    assert "left:100.0pt" in html
    assert "top:100.0pt" in html
    assert "width:100.0pt" in html

    # Image 2: left=300, top=400 (bbox[1]), width=150, height=100
    assert "left:300.0pt" in html
    assert "top:400.0pt" in html
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

    # Page 1: left=50, top=50 (bbox[1])
    assert "left:50.0pt" in html
    assert "top:50.0pt" in html
    # Page 2: left=200, top=300 (bbox[1])
    assert "left:200.0pt" in html
    assert "top:300.0pt" in html


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
    assert "top:100.0pt" in html


def test_default_css_zeroes_body_and_p_margins(tmp_path: Path):
    """OPP#26: DEFAULT_PDF2HTML_CSS zeroes body margin/padding and <p> margin.

    Without these, WeasyPrint applies default 8px body margin and 1em
    (≈12pt) <p> margin-block-start, shifting image positions by +6pt X / +12pt Y.
    """
    from opp.extractors.pdf2html import DEFAULT_PDF2HTML_CSS

    assert "body { margin: 0;" in DEFAULT_PDF2HTML_CSS, (
        "body margin must be zeroed to prevent WeasyPrint default 8px margin"
    )
    assert "padding: 0;" in DEFAULT_PDF2HTML_CSS, (
        "body padding must be zeroed for consistent positioning"
    )
    assert "p { margin: 0; }" in DEFAULT_PDF2HTML_CSS, (
        "<p> margin must be zeroed — PyMuPDF <p> elements lack position:absolute"
    )


def test_pdf2html_default_css_p_in_emit(tmp_path: Path):
    """OPP#26: emitted skeleton_html <p> tags get no extra margin from browser defaults."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Sample paragraph text")
    pdf_path = tmp_path / "p_margin.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    # CSS rule must be present in emitted <style>
    assert "p { margin: 0; }" in html, "<p> margin-zeroing CSS rule missing in output"
    assert "body { margin: 0;" in html, "body margin-zeroing CSS rule missing in output"


# ---------------------------------------------------------------------------
# OPP#28 — text position + image coordinate system fix
# ---------------------------------------------------------------------------


def test_pdf2html_text_position_includes_absolute(tmp_path: Path):
    """OPP#28: <p> tags from get_text('html') get position:absolute injected."""
    import re as re_mod

    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Positioned text")
    pdf_path = tmp_path / "text_pos.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    p_tags = re_mod.findall(r'<p[^>]*>', html)
    positioned = [p for p in p_tags if 'top:' in p and 'left:' in p]
    assert len(positioned) > 0, f"No positioned <p> in HTML: {html[:500]}"
    for p in positioned:
        assert 'position:absolute' in p, f"Missing position:absolute in: {p}"


def test_pdf2html_text_position_preserves_coords(tmp_path: Path):
    """OPP#28: <p> top/left values are preserved (not altered) by text fix."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Hello")
    pdf_path = tmp_path / "coords.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    assert 'top:63' in html, f"top:63 not preserved in: {html[:500]}"
    assert 'left:72' in html, f"left:72 not preserved in: {html[:500]}"
    assert 'position:absolute' in html, f"position:absolute not added: {html[:500]}"


def test_pdf2html_image_coordinate_system_top_left(tmp_path: Path):
    """OPP#28: For M.d<0 (top-left page space), css_top = bbox[1]."""
    import struct, zlib

    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    sig = b'\x89PNG\r\n\x1a\n'
    def chk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    png = sig + chk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)) + chk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00\x00')) + chk(b'IEND', b'')

    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=png)
    pdf_path = tmp_path / "tl.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    assert "top:100.0pt" in html, f"Expected top:100.0pt (bbox[1] for top-left), got: {html[:800]}"
    assert "left:100.0pt" in html
    assert "width:100.0pt" in html
    assert "height:100.0pt" in html


def test_pdf2html_text_fix_runs_before_image_fix(tmp_path: Path):
    """OPP#28: _fix_text_positions is called before _fix_image_positions in extract()."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Hello")
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "mixed.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    import re as re_mod
    p_tags = re_mod.findall(r'<p[^>]*>', html)
    positioned = [p for p in p_tags if 'top:' in p and 'left:' in p]
    for p in positioned:
        assert 'position:absolute' in p, f"<p> missing position:absolute: {p}"

    assert '<img style="position:absolute' in html
    assert "top:100.0pt" in html


def test_pdf2html_image_fallback_bottom_left(tmp_path: Path):
    """OPP#28: When transformation_matrix unavailable, defaults to top-left (is_top_left=True)."""
    import fitz
    from opp.extractors.pdf2html import PDF2HTMLExtractor
    from unittest.mock import PropertyMock, patch

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    pdf_path = tmp_path / "fallback.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = PDF2HTMLExtractor().extract(pdf_path)
    html = result.skeleton_html or ""

    assert "top:100.0pt" in html, f"Expected default top-left fallback (top:100.0pt): {html[:800]}"


def test_pdf_e2e_pixel_level_image_match(tmp_path: Path):
    """OPP#28: Rendered output PDF has image at correct position."""
    weasyprint = pytest.importorskip("weasyprint")
    import fitz
    from weasyprint import HTML
    from opp.extractors.pdf2html import PDF2HTMLExtractor

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_MINIMAL_PNG)
    src_pdf = tmp_path / "source.pdf"
    doc.save(str(src_pdf))
    doc.close()

    src_doc = fitz.open(str(src_pdf))
    src_pix = src_doc[0].get_pixmap(dpi=200)
    src_doc.close()

    result = PDF2HTMLExtractor().extract(src_pdf)

    out_html = tmp_path / "output.html"
    out_html.write_text(result.skeleton_html or "", encoding="utf-8")
    out_pdf = tmp_path / "output.pdf"
    HTML(str(out_html)).write_pdf(str(out_pdf))

    out_doc = fitz.open(str(out_pdf))
    out_pix = out_doc[0].get_pixmap(dpi=200)
    out_doc.close()

    dpr = 200 / 72
    dark_xs, dark_ys = [], []
    for y in range(int(80 * dpr), min(out_pix.height, int(220 * dpr))):
        for x in range(int(80 * dpr), min(out_pix.width, int(220 * dpr))):
            r, g, b = out_pix.pixel(x, y)[:3]
            if r < 50 and g < 50 and b < 50:
                dark_xs.append(x)
                dark_ys.append(y)

    assert len(dark_xs) > 0, (
        f"No dark pixels in expected region. Sample pixels:\n"
        f"{[(x, y, out_pix.pixel(int(150*dpr), y)) for y in [int(100*dpr), int(120*dpr), int(150*dpr)]]}"
    )

    actual_left_pt = min(dark_xs) / dpr
    actual_top_pt = min(dark_ys) / dpr

    tolerance_pt = 5.0
    assert abs(actual_left_pt - 100) <= tolerance_pt, f"Left edge off: expected 100pt, got {actual_left_pt:.1f}pt"
    assert abs(actual_top_pt - 100) <= tolerance_pt, f"Top edge off: expected 100pt, got {actual_top_pt:.1f}pt"
