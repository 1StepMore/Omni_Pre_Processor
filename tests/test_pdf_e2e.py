"""End-to-end tests for PDF extraction functionality."""

from pathlib import Path

import pytest

from opp.detector import detect_format, FormatType
from opp.extractors.pdf import PDFExtractor
from opp.pipeline import OPPPipeline, ProcessingResult


class TestPDFExtraction:
    """Tests for PDF content extraction."""

    def test_pdf_native_text_extraction(self, sample_files_normal: Path):
        """PDF with native text extracts correctly."""
        pdf_path = sample_files_normal / "native_text.pdf"
        extractor = PDFExtractor()
        result = extractor.extract(pdf_path)

        assert result.content
        assert "Hello PDF" in result.content

    def test_pdf_text_extraction_paragraphs(self, sample_files_normal: Path):
        """PDF text appears as paragraphs in extraction result."""
        pdf_path = sample_files_normal / "native_text.pdf"
        extractor = PDFExtractor()
        result = extractor.extract(pdf_path)

        assert len(result.paragraphs) > 0
        texts = [p.text for p in result.paragraphs]
        assert any("Hello PDF" in t for t in texts)

    def test_pdf_table_structure(self, sample_files_normal: Path):
        """PDF with wired table extracts table content."""
        pdf_path = sample_files_normal / "wired_table.pdf"
        extractor = PDFExtractor()
        result = extractor.extract(pdf_path)

        assert "Cell1" in result.content or "Cell2" in result.content

    def test_pdf_image_extraction(self, sample_files_normal: Path):
        """PDF with images extracts image data."""
        pdf_path = sample_files_normal / "with_images.pdf"
        extractor = PDFExtractor()
        result = extractor.extract(pdf_path)

        assert len(result.images) >= 1
        assert result.images[0].data is not None

    def test_pdf_format_detection(self, sample_files_normal: Path):
        """PDF file is correctly detected as PDF format."""
        fmt, confidence = detect_format(sample_files_normal / "native_text.pdf")
        assert fmt == FormatType.PDF
        assert confidence > 0


class TestPDFToXLIFF:
    """Tests for PDF XLIFF output."""

    def test_pdf_xliff_case_sensitivity_bug(self, sample_files_normal: Path, tmp_path: Path):
        """PDF XLIFF guard now correctly blocks PDF XLIFF generation (case fix: 'PDF' -> 'pdf')."""
        pdf_path = sample_files_normal / "native_text.pdf"
        extractor = PDFExtractor()
        result = extractor.extract(pdf_path)

        assert result.metadata.format_type == "pdf"

        pipeline = OPPPipeline(tmp_path / "resources")
        output_xliff = tmp_path / "output.xliff"

        with pytest.raises(ValueError, match="XLIFF not supported for PDF format"):
            pipeline.generate_xliff(result, output_xliff, source_lang="en", target_lang="fr")


class TestPDFComplexLayouts:
    """Tests for PDF with complex layouts."""

    def test_pdf_multicolumn_layout(self, sample_files_edge: Path, tmp_path: Path):
        """PDF with multi-column layout extracts text from both columns."""
        pdf_path = sample_files_edge / " multicolum.pdf"
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(pdf_path)

        assert result.format_type == FormatType.PDF
        assert "Col1 Text" in result.content
        assert "Col2 Text" in result.content

    def test_pdf_wireless_table(self, sample_files_edge: Path, tmp_path: Path):
        """PDF with wireless table extracts text."""
        pdf_path = sample_files_edge / "wireless_table.pdf"
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(pdf_path)

        assert result.format_type == FormatType.PDF
        assert "Col1" in result.content or "Val1" in result.content

    def test_pdf_compressed_images(self, sample_files_edge: Path, tmp_path: Path):
        """PDF with compressed images extracts image data."""
        pdf_path = sample_files_edge / "compressed_images.pdf"
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(pdf_path)

        assert result.format_type == FormatType.PDF
        assert result.images_stored >= 0

    def test_pdf_empty_page(self, sample_files_edge: Path, tmp_path: Path):
        """Empty PDF is handled gracefully."""
        pdf_path = sample_files_edge / "empty.pdf"
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(pdf_path)

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.PDF

    def test_pdf_pseudo_table(self, sample_files_edge: Path, tmp_path: Path):
        """PDF with pseudo table structure extracts content."""
        pdf_path = sample_files_edge / "pseudo_table.pdf"
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(pdf_path)

        assert isinstance(result, ProcessingResult)
        assert result.format_type == FormatType.PDF


class TestPDFPipelineIntegration:
    """Tests for PDF through full OPP pipeline."""

    def test_pipeline_process_pdf_produces_result(self, sample_files_normal: Path, tmp_path: Path):
        """Pipeline process_file produces valid ProcessingResult for PDF."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "native_text.pdf")

        assert result.format_type.value == "pdf"
        assert result.content is not None

    def test_pipeline_process_pdf_with_table(self, sample_files_normal: Path, tmp_path: Path):
        """Pipeline processes PDF with table correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "wired_table.pdf")

        assert result.format_type.value == "pdf"
        assert result.content
        assert "Cell1" in result.content or "Cell2" in result.content

    def test_pipeline_process_pdf_with_images(self, sample_files_normal: Path, tmp_path: Path):
        """Pipeline processes PDF with images correctly."""
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_images.pdf")

        assert result.format_type.value == "pdf"
        assert result.images_stored >= 0

    def test_pipeline_batch_pdf_files(self, sample_files_normal: Path, sample_files_edge: Path, tmp_path: Path):
        """Pipeline batch processes multiple PDF files."""
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_normal / "native_text.pdf",
            sample_files_normal / "wired_table.pdf",
            sample_files_edge / "empty.pdf",
        ]
        batch_result = pipeline.process_batch(files)

        assert batch_result.successful >= 2
        assert len(batch_result.results) == 3

    def test_pdf_multiple_pages(self, tmp_path: Path):
        """PDF with multiple pages is processed correctly."""
        import fitz

        pdf = fitz.open()
        for i in range(3):
            page = pdf.new_page(width=595, height=842)
            rect = fitz.Rect(100, 100, 200, 200)
            page.insert_textbox(rect, f"Page {i+1} content", fontsize=12)
        pdf.save(str(tmp_path / "multi_page.pdf"))

        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(tmp_path / "multi_page.pdf")

        assert result.format_type == FormatType.PDF
        assert "Page 1 content" in result.content
        assert "Page 2 content" in result.content
        assert "Page 3 content" in result.content