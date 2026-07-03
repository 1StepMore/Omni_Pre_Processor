"""Tests for P0-T6 (max_file_size_mb=0 means no limit) and P0-T7 (PDF enum comparison).

P0-T6: max_file_size_mb=0 must mean 'no limit', not 'reject everything > 0 bytes'.
P0-T7: pipeline.generate_xliff must use FormatType.PDF.value (not hardcoded 'pdf').
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from opp.detector import FormatType
from opp.pipeline import OPPPipeline
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult


# ---------------------------------------------------------------------------
# P0-T6: max_file_size_mb=0 should NOT reject any file
# ---------------------------------------------------------------------------

class TestMaxFileSizeZero:
    """P0-T6: When max_file_size_mb=0, file-size check must be skipped."""

    def test_process_file_max_size_zero_does_not_reject(self, tmp_path: Path):
        """max_file_size_mb=0 must mean 'no limit' (not 'reject > 0 bytes')."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world" * 100)  # > 0 bytes

        pipeline = OPPPipeline(
            resource_storage_dir=tmp_path / "resources",
            max_file_size_mb=0,
        )
        # Should NOT raise ValueError for file size.
        # Other errors (e.g., unknown format) are fine — we only care about size.
        try:
            pipeline.process_file(test_file)
        except ValueError as e:
            if "exceeds limit" in str(e):
                pytest.fail(
                    f"max_file_size_mb=0 should mean 'no limit', but file was rejected: {e}"
                )
            # Other ValueErrors are not what we're testing

    def test_process_file_max_size_positive_rejects_oversized(self, tmp_path: Path):
        """Sanity: max_file_size_mb=1 should reject files > 1MB."""
        big_file = tmp_path / "big.txt"
        big_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        pipeline = OPPPipeline(
            resource_storage_dir=tmp_path / "resources",
            max_file_size_mb=1,
        )
        with pytest.raises(ValueError, match="exceeds limit"):
            pipeline.process_file(big_file)

    def test_process_file_max_size_none_rejects(self, tmp_path: Path):
        """Sanity: max_file_size_mb=None should also reject (current behavior)."""
        big_file = tmp_path / "big.txt"
        big_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        pipeline = OPPPipeline(
            resource_storage_dir=tmp_path / "resources",
            max_file_size_mb=None,
        )
        # max_file_size_mb=None means the check is skipped (no limit)
        try:
            pipeline.process_file(big_file)
        except ValueError as e:
            if "exceeds limit" in str(e):
                pytest.fail(
                    "max_file_size_mb=None should mean 'no limit', "
                    f"but file was rejected: {e}"
                )


# ---------------------------------------------------------------------------
# P0-T7: PDF guard must use FormatType.PDF.value, not hardcoded 'pdf'
# ---------------------------------------------------------------------------

class TestPDFXliffGuardEnum:
    """P0-T7: generate_xliff must compare against FormatType.PDF.value."""

    def test_generate_xliff_rejects_pdf_with_enum_value(self, tmp_path: Path):
        """Guard must fire when format_type is FormatType.PDF.value."""
        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type=FormatType.PDF.value),
        )
        with pytest.raises(ValueError, match=r"XLIFF not supported for PDF"):
            pipeline.generate_xliff(
                result, tmp_path / "out.xlf", source_lang="en", target_lang="zh"
            )

    def test_generate_xliff_guard_survives_enum_value_change(self, tmp_path: Path):
        """P0-T7 core test: If FormatType.PDF.value changes, the guard must
        still fire because it references the enum constant, not a hardcoded string.

        We temporarily monkeypatch FormatType.PDF.value to a different string
        and verify the guard adapts. A hardcoded 'pdf' would break.
        """
        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type="pdf_alt"),
        )
        # Temporarily change the enum value
        original = FormatType.PDF.value
        try:
            FormatType._value2member_map_.pop(original, None)
            FormatType.PDF._value_ = "pdf_alt"
            FormatType._value2member_map_["pdf_alt"] = FormatType.PDF

            with pytest.raises(ValueError, match=r"XLIFF not supported for PDF"):
                pipeline.generate_xliff(
                    result,
                    tmp_path / "out.xlf",
                    source_lang="en",
                    target_lang="zh",
                )
        finally:
            # Restore original
            FormatType._value2member_map_.pop("pdf_alt", None)
            FormatType.PDF._value_ = original
            FormatType._value2member_map_[original] = FormatType.PDF
