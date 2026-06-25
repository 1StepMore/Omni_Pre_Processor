"""Tests for Issue #9: PDF OCR lang respects OPP_OCR_LANG env var.

Previously, `_ocr_page` always called `_ocr_tesseract(img, lang="eng")`,
preventing OCR of non-English PDFs/images. Now it reads `OPP_OCR_LANG`
(defaults to "eng" for backward compat).
"""

from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from opp.extractors.pdf import PDFExtractor, _get_ocr_lang


# ── _get_ocr_lang() unit tests ──────────────────────────────────────


class TestGetOcrLang:
    """Unit tests for the module-level _get_ocr_lang() helper."""

    def test_default_ocr_lang_is_eng(self, monkeypatch):
        """With no env var set, returns 'eng'."""
        monkeypatch.delenv("OPP_OCR_LANG", raising=False)
        assert _get_ocr_lang() == "eng"

    def test_ocr_lang_reads_env_var(self, monkeypatch):
        """With OPP_OCR_LANG=chi_sim, returns 'chi_sim'."""
        monkeypatch.setenv("OPP_OCR_LANG", "chi_sim")
        assert _get_ocr_lang() == "chi_sim"

    def test_ocr_lang_japanese(self, monkeypatch):
        """Supports Japanese language code."""
        monkeypatch.setenv("OPP_OCR_LANG", "jpn")
        assert _get_ocr_lang() == "jpn"

    def test_ocr_lang_french(self, monkeypatch):
        """Supports French language code."""
        monkeypatch.setenv("OPP_OCR_LANG", "fra")
        assert _get_ocr_lang() == "fra"


# ── Integration: _ocr_page uses configured lang ─────────────────────


class TestOcrPageUsesConfiguredLang:
    """Verify that _ocr_page passes the configured lang to _ocr_tesseract,
    not the old hardcoded 'eng'."""

    def test_ocr_tesseract_called_with_configured_lang(self, tmp_path, monkeypatch):
        """Mock _ocr_tesseract and verify it's called with the configured
        lang from OPP_OCR_LANG, not hardcoded 'eng'."""
        monkeypatch.setenv("OPP_OCR_LANG", "chi_sim")

        # Create a minimal PDF with an empty page (triggers OCR path)
        doc = fitz.open()
        doc.new_page()
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        ext = PDFExtractor()
        with patch.object(ext, "_ocr_tesseract", return_value="some text") as mock_ocr:
            # Directly call _ocr_page on a real page
            fitz_doc = fitz.open(str(pdf_path))
            ext._ocr_page(fitz_doc[0], 0)
            fitz_doc.close()

        # Verify _ocr_tesseract was called with lang="chi_sim"
        assert mock_ocr.call_count == 1
        call_kwargs = mock_ocr.call_args
        assert call_kwargs[1].get("lang") == "chi_sim" or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "chi_sim"
        ), (
            f"Expected _ocr_tesseract called with lang='chi_sim', "
            f"got {call_kwargs}"
        )

    def test_ocr_page_default_lang_is_eng(self, tmp_path, monkeypatch):
        """With no env var, _ocr_page should call _ocr_tesseract with 'eng'."""
        monkeypatch.delenv("OPP_OCR_LANG", raising=False)

        doc = fitz.open()
        doc.new_page()
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        ext = PDFExtractor()
        with patch.object(ext, "_ocr_tesseract", return_value="text") as mock_ocr:
            fitz_doc = fitz.open(str(pdf_path))
            ext._ocr_page(fitz_doc[0], 0)
            fitz_doc.close()

        assert mock_ocr.call_count == 1
        call_kwargs = mock_ocr.call_args
        assert call_kwargs[1].get("lang") == "eng" or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "eng"
        ), (
            f"Expected _ocr_tesseract called with lang='eng', "
            f"got {call_kwargs}"
        )

    def test_full_extract_uses_configured_lang(self, tmp_path, monkeypatch):
        """End-to-end: extract() on an image-only PDF uses the configured
        lang from OPP_OCR_LANG."""
        monkeypatch.setenv("OPP_OCR_LANG", "kor")

        # Build an image-only PDF (no text layer → triggers OCR fallback)
        text_doc = fitz.open()
        page = text_doc.new_page()
        page.insert_text((50, 50), "Korean text here")
        tmp_text = tmp_path / "tmp_text.pdf"
        text_doc.save(str(tmp_text))
        text_doc.close()

        src = fitz.open(str(tmp_text))
        img_doc = fitz.open()
        for p in src:
            pix = p.get_pixmap(dpi=150)
            new_page = img_doc.new_page(width=p.rect.width, height=p.rect.height)
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

        ext = PDFExtractor()
        with patch.object(ext, "_ocr_tesseract", return_value="translated") as mock_ocr:
            res = ext.extract(img_pdf)

        # OCR should have been called with lang="kor"
        assert mock_ocr.call_count >= 1
        call_kwargs = mock_ocr.call_args
        assert call_kwargs[1].get("lang") == "kor" or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "kor"
        ), (
            f"Expected _ocr_tesseract called with lang='kor', "
            f"got {call_kwargs}"
        )
