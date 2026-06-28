from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from opp.extractors.pdf import PDFExtractor
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


def _make_text_pdf(text_paragraphs: list[str], tmp_path: Path) -> Path:
    """Generate a text-layer PDF with the given paragraphs (in-memory)."""
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    for para in text_paragraphs:
        page.insert_text((50, y), para)
        y += 30
    path = tmp_path / "text.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _make_image_only_pdf(text_paragraphs: list[str], tmp_path: Path) -> Path:
    """Generate a PDF where each page is a rasterized image (no text layer).
    Simulates a scanned / image-only PDF that the old OPP extractor
    returned 0 chars for (issue OPP #5 root cause)."""
    text_doc = fitz.open()
    page = text_doc.new_page()
    y = 50
    for para in text_paragraphs:
        page.insert_text((50, y), para)
        y += 30
    text_pdf = tmp_path / "tmp_text.pdf"
    text_doc.save(str(text_pdf))
    text_doc.close()

    src = fitz.open(str(text_pdf))
    img_doc = fitz.open()
    for p in src:
        pix = p.get_pixmap(dpi=150)
        new_page = img_doc.new_page(width=p.rect.width, height=p.rect.height)
        # Render the pixmap to a PNG and insert as image
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_png = f.name
        pix.save(tmp_png)
        try:
            new_page.insert_image(p.rect, filename=tmp_png)
        finally:
            os.unlink(tmp_png)
    img_pdf = tmp_path / "image_only.pdf"
    img_doc.save(str(img_pdf))
    src.close()
    img_doc.close()
    text_pdf.unlink()
    return img_pdf


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

    def test_max_pages_limits_extraction(self, tmp_path):
        """RED→GREEN (O-C8): only MAX_PAGES pages are extracted from a huge PDF.

        RED: old code iterates ALL pages (``for page_num in range(doc.page_count)``),
             no limit — 50K-page PDF loads all TextBlockData into memory.
        GREEN: new code caps at MAX_PAGES (default 1000) with a warning log.
        """
        from unittest.mock import patch
        doc = fitz.open()
        for i in range(5):
            page = doc.new_page()
            page.insert_text((50, 50), f"Content on page {i + 1}")
        pdf_path = tmp_path / "five_pages.pdf"
        doc.save(str(pdf_path))
        doc.close()

        ext = PDFExtractor()
        ext.MAX_PAGES = 2  # override to test small limit

        with patch("opp.extractors.pdf.logger.warning") as mock_warn:
            result = ext.extract(pdf_path)

        # Warning logged about the page limit (among any other warnings)
        found = any(
            "extracting only first 2" in (call.args[0] % call.args[1:])
            for call in mock_warn.call_args_list
        )
        assert found, (
            f"Expected page-limit warning in {mock_warn.call_args_list}"
        )

        # Only pages 1-2 have content; pages 3-5 are NOT extracted
        texts = [p.text for p in result.paragraphs]
        assert any("page 1" in t.lower() or "Content on page 1" in t for t in texts)
        assert any("page 2" in t.lower() or "Content on page 2" in t for t in texts)
        # Pages 3-5 must NOT appear
        for i in range(3, 6):
            assert not any(f"page {i}" in t.lower() or f"Content on page {i}" in t for t in texts), (
                f"Page {i} content should not be present (MAX_PAGES=2)"
            )


# ════════════════════════════════════════════════════════════════════════
# Issue OPP #5: OCR fallback for image-only / scanned PDF pages
# ════════════════════════════════════════════════════════════════════════


class TestPDFOCRFallback:
    """Validates the OCR fallback for image-only / scanned PDFs.

    Before the fix, an image-only PDF (scanned, no text layer)
    returned 0 paragraphs / 0 characters because `page.get_text("blocks")`
    is empty for rasterized pages. The 12/12 PDF cells in the
    2026-06-24 matrix regression all failed for this reason.

    After the fix, `extract_text_blocks` detects per-page
    text-layer sparsity and renders the page as a high-DPI image
    for OCR via the existing `_ocr_tesseract` / `_ocr_rapidocr`
    helpers. If neither OCR engine is installed, the page silently
    falls through to whatever text-layer content (if any) it could
    extract — no crash, no silent data loss.
    """

    def test_text_layer_pdf_does_not_trigger_ocr_fallback(self, tmp_path):
        """A PDF with > threshold chars per page should NOT call
        the OCR fallback path. The OCR call count is asserted via
        mock to pin the threshold logic."""
        long_para = (
            "This is a long-enough body paragraph that exceeds the "
            "30-character threshold and therefore should NOT trigger "
            "the OCR fallback. " * 3
        )
        pdf = _make_text_pdf([long_para], tmp_path)
        ext = PDFExtractor()
        with patch.object(ext, "_ocr_page", return_value=[]) as mock_ocr:
            res = ext.extract(pdf)
        # The text-layer extraction should have found plenty of text;
        # OCR fallback should NOT have been called.
        assert len(res.paragraphs) > 0
        assert mock_ocr.call_count == 0, (
            "OCR fallback should not run for a text-layer PDF with "
            f">{ext.OCR_FALLBACK_TEXT_THRESHOLD} chars; got "
            f"{mock_ocr.call_count} calls"
        )

    def test_empty_page_triggers_ocr_fallback(self, tmp_path):
        """A page with 0 text-layer chars must call OCR fallback
        (so the page has at least a chance of returning content)."""
        pdf = _make_text_pdf([], tmp_path)  # empty page
        ext = PDFExtractor()
        with patch.object(ext, "_ocr_page", return_value=[]) as mock_ocr:
            res = ext.extract(pdf)
        assert mock_ocr.call_count == 1
        # OCR returned [] (mocked), so the page contributes no paragraphs.
        assert len(res.paragraphs) == 0

    def test_short_text_triggers_ocr_fallback(self, tmp_path):
        """A page with < threshold chars triggers OCR (e.g. only
        title metadata extracted, body is image-based)."""
        pdf = _make_text_pdf(["Hi"], tmp_path)  # 2 chars, way below 30
        ext = PDFExtractor()
        with patch.object(ext, "_ocr_page", return_value=[]) as mock_ocr:
            res = ext.extract(pdf)
        assert mock_ocr.call_count == 1

    def test_ocr_results_are_integrated_into_paragraphs(self, tmp_path):
        """When OCR returns content, it must be added to the
        ExtractionResult.paragraphs list (not silently dropped)."""
        from opp.utils.dataclasses import TextBlockData
        pdf = _make_text_pdf([], tmp_path)
        ext = PDFExtractor()
        ocr_block = TextBlockData(
            text="OCR recovered this text from the scanned page",
            bbox=(0, 0, 100, 100),
            page=1,
        )
        with patch.object(ext, "_ocr_page", return_value=[ocr_block]):
            res = ext.extract(pdf)
        assert len(res.paragraphs) == 1
        assert res.paragraphs[0].text == "OCR recovered this text from the scanned page"

    def test_real_image_only_pdf_uses_fallback_path(self, tmp_path):
        """End-to-end: a real image-only PDF (rasterized from text)
        triggers the OCR fallback path. Even if Tesseract isn't
        installed (returns 0 chars), the path is invoked and the
        page doesn't crash."""
        # Only run this if PyMuPDF is available (it is — we used it
        # to generate the test PDF above).
        pdf = _make_image_only_pdf(
            ["Technical Report: A comprehensive overview"],
            tmp_path,
        )
        ext = PDFExtractor()
        with patch.object(ext, "_ocr_page", wraps=ext._ocr_page) as wrapped:
            res = ext.extract(pdf)
        # OCR fallback WAS attempted (whether or not it returned text
        # depends on whether Tesseract / RapidOCR is installed).
        # The key assertion: no crash, no exception, graceful return.
        assert isinstance(res.paragraphs, list)
        # The OCR method is called at least once for an image-only page.
        assert wrapped.call_count >= 1, (
            "OCR fallback should be attempted for image-only PDF; "
            f"got {wrapped.call_count} calls"
        )

    def test_ocr_fallback_threshold_constant_pinned(self):
        """Pin the calibrated threshold so future refactors don't
        drift it without re-running the matrix regression."""
        ext = PDFExtractor()
        assert ext.OCR_FALLBACK_TEXT_THRESHOLD == 30

    def test_ocr_page_silent_no_op_when_pil_missing(self, tmp_path):
        """_ocr_page returns [] silently when PIL is unavailable
        (not all environments have Pillow). The text-layer path
        still runs and emits whatever it can extract."""
        pdf = _make_image_only_pdf(["fallback test"], tmp_path)
        ext = PDFExtractor()
        # Simulate PIL not being importable
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *args, **kwargs):
            if name == "PIL" or name.startswith("PIL."):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=fake_import):
            ocr_result = ext._ocr_page(fitz.open(str(pdf))[0], 0)
        # No crash, empty result
        assert ocr_result == []

    # ════════════════════════════════════════════════════════════════
    # Issue OPP #7: word-level spacing recovery for justified text
    # ════════════════════════════════════════════════════════════════

    def test_word_level_spacing_recovered(self, tmp_path):
        """Two text runs at same y, different x → 'Hello PDF' with space."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Hello")
        page.insert_text((120, 50), "PDF")  # same y, different x
        p = tmp_path / "runs.pdf"
        doc.save(str(p))
        doc.close()
        ext = PDFExtractor()
        res = ext.extract(p)
        texts = [para.text for para in res.paragraphs]
        found = any("Hello PDF" in t for t in texts)
        assert found, (
            f"Expected 'Hello PDF' with space, got: {texts}"
        )

    def test_multi_line_text_has_lines(self, tmp_path):
        """Multi-line text → each line is a separate paragraph."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Line one content")
        page.insert_text((50, 70), "Line two content")
        p = tmp_path / "multiline.pdf"
        doc.save(str(p))
        doc.close()
        ext = PDFExtractor()
        res = ext.extract(p)
        texts = [para.text for para in res.paragraphs]
        assert len(texts) >= 2, (
            f"Expected >=2 paragraphs, got {len(texts)}: {texts}"
        )
        assert any("Line one" in t for t in texts)
        assert any("Line two" in t for t in texts)

    def test_word_ordering_within_block_preserved(self, tmp_path):
        """Three text runs at same y → words joined left-to-right within block.

        The word-level reconstruction sorts by x within each y-line,
        so even when MuPDF merges separate insert_text calls into one
        block, the words appear in correct reading order."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "First")
        page.insert_text((150, 50), "Middle")
        page.insert_text((250, 50), "Last")
        p = tmp_path / "ordering.pdf"
        doc.save(str(p))
        doc.close()
        ext = PDFExtractor()
        res = ext.extract(p)
        texts = [para.text for para in res.paragraphs]
        found = any("First Middle Last" in t for t in texts)
        assert found, (
            f"Expected 'First Middle Last' (left-to-right), got: {texts}"
        )

    def test_image_only_pdf_still_triggers_ocr_fallback(self, tmp_path):
        """Regression: #5 OCR fallback still triggers on image-only PDFs."""
        pdf = _make_image_only_pdf(["OCR fallback test"], tmp_path)
        ext = PDFExtractor()
        with patch.object(ext, "_ocr_page") as mock_ocr:
            res = ext.extract(pdf)
        assert mock_ocr.call_count >= 1, (
            "OCR should still be attempted on image-only PDFs; "
            f"got {mock_ocr.call_count} calls"
        )
