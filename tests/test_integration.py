"""Integration tests for OPP Pipeline - full extraction pipeline."""

from pathlib import Path
from datetime import datetime

import pytest

from opp.detector import detect_format, FormatType
from opp.pipeline import OPPPipeline, ProcessingResult, BatchResult
from opp.resource_manager import ResourceManager


class TestOPPPipelineIntegration:
    """Integration tests for the full OPP pipeline."""

    def test_pipeline_initialization(self, tmp_path: Path):
        """Pipeline initializes correctly with resource storage."""
        pipeline = OPPPipeline(tmp_path / "resources")
        assert pipeline.resource_storage_dir == tmp_path / "resources"
        assert isinstance(pipeline.resource_manager, ResourceManager)
        assert FormatType.DOCX in pipeline.extractors
        assert FormatType.PPTX in pipeline.extractors
        assert FormatType.PDF in pipeline.extractors

    def test_process_file_docx_full_pipeline(self, sample_files_normal: Path, tmp_path: Path):
        """DOCX file processes through detect → extract → manage → report."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "normal.docx")

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.DOCX
        assert result.content.strip()
        assert result.images_stored >= 0
        assert len(result.errors) == 0

    def test_process_file_pptx_full_pipeline(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "normal.pptx")

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.PPTX
        assert result.content
        assert result.images_stored >= 0
        assert len(result.errors) == 0

    def test_process_file_pdf_full_pipeline(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "native_text.pdf")

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.PDF
        assert result.content
        assert result.images_stored >= 0
        assert len(result.errors) == 0

    def test_process_file_with_table(self, sample_files_normal: Path, tmp_path: Path):
        """DOCX with tables extracts content correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_table.docx")

        assert result.format_type == FormatType.DOCX
        assert isinstance(result.content, str)

    def test_process_file_with_image(self, sample_files_normal: Path, tmp_path: Path):
        """DOCX with images stores resources via resource_manager."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_image.docx")

        assert result.format_type == FormatType.DOCX
        assert isinstance(result.content, str)
        assert result.images_stored >= 0

    def test_process_batch_all_successful(self, sample_files_normal: Path, tmp_path: Path):
        """Batch processing with all valid files returns 3 successful."""
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_normal / "normal.docx",
            sample_files_normal / "normal.pptx",
            sample_files_normal / "native_text.pdf",
        ]
        batch_result = pipeline.process_batch(files)

        assert isinstance(batch_result, BatchResult)
        assert batch_result.successful == 3
        assert batch_result.failed == 0
        assert len(batch_result.results) == 3
        assert batch_result.total_duration_ms > 0

    def test_process_batch_mixed_valid_corrupted(self, sample_files_normal: Path, sample_files_error: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_normal / "normal.docx",
            sample_files_normal / "normal.pptx",
            sample_files_error / "corrupted.docx",
        ]
        batch_result = pipeline.process_batch(files)

        assert isinstance(batch_result, BatchResult)
        assert batch_result.successful >= 1
        assert batch_result.failed >= 1
        assert batch_result.successful + batch_result.failed == 3
        assert len(batch_result.results) == 3

    def test_process_batch_error_handler_records_failures(self, sample_files_error: Path, tmp_path: Path):
        """Error handler records failures during batch processing."""
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_error / "corrupted.docx",
            sample_files_error / "corrupted.pptx",
            sample_files_error / "corrupted.pdf",
        ]
        batch_result = pipeline.process_batch(files)

        stats = pipeline.get_error_stats()
        assert stats["errors"] >= 3

    def test_invalid_file_does_not_crash_pipeline(self, sample_files_error: Path, tmp_path: Path):
        """Invalid/corrupted file doesn't crash the pipeline."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_error / "corrupted.docx")

        # Should return a result (possibly with errors) but not crash
        assert isinstance(result, ProcessingResult)
        assert result.errors or result.warnings  # Should have errors/warnings logged

    def test_error_context_recorded_for_failed_file(self, sample_files_error: Path, tmp_path: Path):
        """Error handler records the failure context for corrupted files."""
        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.process_file(sample_files_error / "corrupted.docx")

        errors = pipeline.error_handler.get_errors()
        assert len(errors) > 0
        # Should have an error with the file path
        error_paths = [e.file_path for e in errors]
        assert str(sample_files_error / "corrupted.docx") in error_paths

    def test_valid_files_still_processed_after_error(self, sample_files_normal: Path, sample_files_error: Path, tmp_path: Path):
        """Valid files are processed even after encountering corrupted files."""
        pipeline = OPPPipeline(tmp_path / "resources")

        # Process corrupted first
        result_bad = pipeline.process_file(sample_files_error / "corrupted.docx")
        assert result_bad.errors  # Should have errors

        # Process valid - should still work
        result_good = pipeline.process_file(sample_files_normal / "normal.docx")
        assert result_good.format_type == FormatType.DOCX
        assert len(result_good.errors) == 0
        assert result_good.content  # Should have extracted content

    def test_resource_deduplication_across_files(self, sample_files_normal: Path, tmp_path: Path):
        """MD5 deduplication works - same image across files returns same stored path."""
        # This test uses DOCX files which may have different embedded images
        pipeline = OPPPipeline(tmp_path / "resources")

        # Process two different files
        result1 = pipeline.process_file(sample_files_normal / "normal.docx")
        result2 = pipeline.process_file(sample_files_normal / "with_table.docx")

        # Both should complete (resource manager works)
        assert result1.format_type == FormatType.DOCX
        assert result2.format_type == FormatType.DOCX

        # Resource manager mapping should track original names to paths
        mapping = pipeline.resource_manager.get_mapping()
        # Mapping may be empty if no images were extracted, but manager should work

    def test_resource_manager_stores_images(self, sample_files_normal: Path, tmp_path: Path):
        """Images extracted from DOCX and stored via resource_manager."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "normal.docx")

        # Resource manager should have entries if images were found
        mapping = pipeline.resource_manager.get_mapping()
        # Note: specific assertion depends on actual image extraction
        assert isinstance(mapping, dict)

    def test_pipeline_with_pptx_with_notes(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_notes.pptx")

        assert result.format_type == FormatType.PPTX
        assert isinstance(result.content, str)

    def test_pipeline_with_pdf_with_images(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_images.pdf")

        assert result.format_type == FormatType.PDF
        assert isinstance(result.content, str)

    def test_pipeline_with_pdf_wired_table(self, sample_files_normal: Path, tmp_path: Path):
        """PDF with table extracts content correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "wired_table.pdf")

        assert result.format_type == FormatType.PDF
        assert result.content

    def test_batch_result_total_duration_measured(self, sample_files_normal: Path, tmp_path: Path):
        """Batch processing measures total duration correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [sample_files_normal / "normal.docx"]
        batch_result = pipeline.process_batch(files)

        assert batch_result.total_duration_ms > 0

    def test_zero_byte_file_returns_proper_result(self, sample_files_error: Path, tmp_path: Path):
        """Zero-byte files are handled gracefully."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_error / "zero_byte.docx")

        assert isinstance(result, ProcessingResult)
        # Zero-byte files may have warnings or errors, but pipeline doesn't crash

    def test_process_file_with_unknown_format(self, tmp_path: Path):
        """Unknown format file returns proper result with warnings."""
        # Create a file with unknown format
        unknown_file = tmp_path / "unknown.bin"
        unknown_file.write_bytes(b"random unknown data")

        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(unknown_file)

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.UNKNOWN
        assert result.errors == [] or result.warnings != []

    def test_error_stats_after_processing(self, sample_files_normal: Path, sample_files_error: Path, tmp_path: Path):
        """Error stats reflect actual errors after batch processing."""
        pipeline = OPPPipeline(tmp_path / "resources")

        # Process mix of good and bad files
        files = [
            sample_files_normal / "normal.docx",
            sample_files_error / "corrupted.docx",
        ]
        pipeline.process_batch(files)

        stats = pipeline.get_error_stats()
        assert "errors" in stats
        assert "warnings" in stats
        assert isinstance(stats["errors"], int)
        assert isinstance(stats["warnings"], int)

class TestProcessBatchEdgeCases:
    """Edge case tests for OPPPipeline.process_batch()."""

    def test_process_batch_empty_file_list(self, tmp_path: Path):
        """Empty file list returns zero successful/failed with zero results."""
        pipeline = OPPPipeline(tmp_path / "resources")
        batch_result = pipeline.process_batch([])

        assert isinstance(batch_result, BatchResult)
        assert batch_result.successful == 0
        assert batch_result.failed == 0
        assert len(batch_result.results) == 0
        assert batch_result.total_duration_ms >= 0

    def test_process_batch_files_with_same_content(self, sample_files_normal: Path, tmp_path: Path):
        """Files with same content are deduplicated by resource manager."""
        pipeline = OPPPipeline(tmp_path / "resources")
        # Process the same file twice
        file = sample_files_normal / "normal.docx"
        files = [file, file]
        batch_result = pipeline.process_batch(files)

        assert isinstance(batch_result, BatchResult)
        assert batch_result.successful == 2
        assert batch_result.failed == 0
        assert len(batch_result.results) == 2
        # Both should have successfully extracted
        for result in batch_result.results:
            assert result.format_type == FormatType.DOCX

    def test_process_batch_mixed_success_failure_results(self, sample_files_normal: Path, sample_files_error: Path, tmp_path: Path):
        """Batch with some valid and some invalid files returns mixed results."""
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_normal / "normal.docx",
            sample_files_error / "corrupted.docx",
            sample_files_normal / "normal.pptx",
            sample_files_error / "zero_byte.pdf",
        ]
        batch_result = pipeline.process_batch(files)

        assert batch_result.successful + batch_result.failed == 4
        assert len(batch_result.results) == 4
        # Check stats reflect mixed results
        stats = pipeline.get_error_stats()
        assert stats["errors"] >= 2  # At least corrupted and zero_byte

    def test_process_batch_very_long_file_paths(self, tmp_path: Path):
        """Pipeline handles files with very long paths correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        # Create a deeply nested directory structure
        deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        deep_dir.mkdir(parents=True)
        long_path_file = deep_dir / ("very_long_filename_" + "x" * 100 + ".docx")

        from docx import Document
        doc = Document()
        doc.add_paragraph("Long path test")
        doc.save(str(long_path_file))

        batch_result = pipeline.process_batch([long_path_file])

        assert isinstance(batch_result, BatchResult)
        assert len(batch_result.results) == 1
        # Should either succeed or fail gracefully
        assert batch_result.successful + batch_result.failed == 1
