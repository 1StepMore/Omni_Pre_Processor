"""Regression test for the PDF→XLIFF guard in OPP pipeline.

Background: The guard at `pipeline.py:125` is `format_type == "pdf"`. A
prior version used `"PDF"` (uppercase) which never matched because
`FormatType.PDF.value` is `"pdf"`. The mismatch silently let PDF→XLIFF
through and produced broken output. The fix is in place, but this test
locks the behaviour so a future refactor cannot regress it.

Tested for:
- Direct `OPPPipeline.generate_xliff()` on a PDF extraction result.
- End-to-end `OPPPipeline.process_file()` + `target_format="xlf"`.

Runs without external PDF libraries (uses a minimal magic-byte stub).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from opp.detector import FormatType
from opp.pipeline import OPPPipeline
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult


def _stub_pdf(path: Path) -> Path:
    """Write a minimal file that OPP's detector identifies as PDF.

    The detector matches on the `%PDF-` magic prefix. We do NOT need
    a real PDF; the guard must fire on format detection alone.
    """
    path.write_bytes(b"%PDF-1.4\n%minimal stub for guard test\n%%EOF\n")
    return path


class TestPDFXliffGuard:
    def test_generate_xliff_raises_value_error_for_pdf_result(self, tmp_path: Path):
        """Direct unit test: construct a PDF ExtractionResult and assert
        generate_xliff raises ValueError with the expected message.

        The guard at pipeline.py:125 is exact-match on lowercase 'pdf'
        because FormatType.PDF.value == 'pdf'. Any uppercase variant
        would silently let PDF→XLIFF through (the historical bug).
        """
        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        pdf_result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type="pdf"),
        )
        out_xlf = tmp_path / "out.xlf"
        with pytest.raises(ValueError, match=r"XLIFF not supported for PDF"):
            pipeline.generate_xliff(
                pdf_result, out_xlf, source_lang="en", target_lang="zh"
            )

    def test_generate_xliff_passes_for_non_pdf(self, tmp_path: Path):
        """Sanity: the guard must NOT block non-PDF formats."""
        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        docx_result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type="docx"),
        )
        out_xlf = tmp_path / "out.xlf"
        out_xlf.write_text("<xliff/>", encoding="utf-8")
        try:
            pipeline.generate_xliff(
                docx_result, out_xlf, source_lang="en", target_lang="zh"
            )
        except ValueError as e:
            if "XLIFF not supported for PDF" in str(e):
                pytest.fail(
                    f"Guard fired for non-PDF format: format_type='docx', err={e}"
                )


def _make_real_pdf(path: Path) -> Path:
    """Generate a small real, parseable PDF via PyMuPDF.

    The guard must be tested against a REAL PDF: a `%PDF-` magic-byte stub
    would fail inside PDF2HTMLExtractor (fitz.open) before generate_xliff
    ever runs, never exercising the guard on the live path.
    """
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF guard")
    doc.save(str(path))
    doc.close()
    return path


class TestPDFXliffGuardCLI:
    """CLI-level regression: the guard must fire on the LIVE CLI path.

    The unit tests above hand-build ``ExtractionResult(format_type="pdf")``,
    but the live CLI never produced such a result for PDF input: since
    commit c0caeb2 (2026-06-27) ALL PDF inputs route through
    PDF2HTMLExtractor, which relabeled ``result.metadata.format_type`` to
    ``"html"`` — silently bypassing the guard at pipeline.py:130. The CLI
    exited 0 and wrote a broken .xlf (T2 re-occurrence, format-relabel
    variant). These tests run the REAL CLI end-to-end so the guard is
    locked on the live path, not just on hand-built unit results.
    """

    def _run_cli(self, pdf: Path, out_dir: Path, target_format: str):
        import subprocess
        import sys

        return subprocess.run(
            [
                sys.executable, "-m", "opp.cli", str(pdf),
                "--target-format", target_format,
                "--source-lang", "en",
                "--target-lang", "zh",
                "--output-dir", str(out_dir),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )

    def test_cli_refuses_pdf_xliff(self, tmp_path: Path):
        """`opp <pdf> --target-format xlf` must exit 1 with the guard
        message on stderr, and MUST NOT write a .xlf."""
        pdf = _make_real_pdf(tmp_path / "sample.pdf")
        out_dir = tmp_path / "out"
        proc = self._run_cli(pdf, out_dir, "xlf")

        assert proc.returncode == 1, (
            f"expected exit 1, got {proc.returncode}; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        assert "XLIFF not supported for PDF format" in proc.stderr, (
            f"guard message missing from stderr: {proc.stderr!r}"
        )
        assert not (out_dir / "sample.xlf").exists(), (
            "a .xlf was produced — the guard was bypassed"
        )

    def test_cli_refuses_pdf_both(self, tmp_path: Path):
        """`--target-format both` on a PDF must ALSO fail on the xlf half
        (md may be written first, but no .xlf may exist and exit must be 1)."""
        pdf = _make_real_pdf(tmp_path / "sample.pdf")
        out_dir = tmp_path / "out"
        proc = self._run_cli(pdf, out_dir, "both")

        assert proc.returncode == 1, (
            f"expected exit 1 for --target-format both, got {proc.returncode}; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        assert "XLIFF not supported for PDF format" in proc.stderr, (
            f"guard message missing from stderr: {proc.stderr!r}"
        )
        assert not (out_dir / "sample.xlf").exists(), (
            "a .xlf was produced — the guard was bypassed on the 'both' path"
        )

    def test_cli_pdf_md_still_works(self, tmp_path: Path):
        """PDF→MD extraction must remain unaffected (exit 0)."""
        pdf = _make_real_pdf(tmp_path / "sample.pdf")
        out_dir = tmp_path / "out"
        proc = self._run_cli(pdf, out_dir, "md")

        assert proc.returncode == 0, (
            f"expected exit 0 for --target-format md, got {proc.returncode}; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        assert (out_dir / "sample.md").exists()

    def test_cli_docx_xliff_unaffected(self, tmp_path: Path):
        """Non-PDF formats must be unaffected: DOCX→XLIFF still exits 0."""
        import subprocess
        import sys

        from docx import Document

        docx_path = tmp_path / "sample.docx"
        doc = Document()
        doc.add_paragraph("Hello DOCX guard")
        doc.save(str(docx_path))

        out_dir = tmp_path / "out"
        proc = self._run_cli(docx_path, out_dir, "xlf")

        assert proc.returncode == 0, (
            f"expected exit 0 for DOCX→XLIFF, got {proc.returncode}; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        assert (out_dir / "sample.xlf").exists()
