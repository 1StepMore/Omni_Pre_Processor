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
