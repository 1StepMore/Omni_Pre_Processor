"""End-to-end tests for PPTX extraction and output generation."""

from pathlib import Path

import pytest

from opp.extractors.pptx import PPTXExtractor
from opp.pipeline import OPPPipeline
from opp.utils.dataclasses import ExtractionResult, SlideData


class TestPPTXExtraction:
    """Test PPTX content extraction - shapes, notes, slides."""

    def test_pptx_normal_multiple_shapes(self, sample_files_normal: Path):
        pptx_path = sample_files_normal / "normal.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        assert isinstance(result, ExtractionResult)
        texts = [p.text for p in result.paragraphs]
        assert "Text 1" in texts
        assert "Text 2" in texts
        assert "Text 3" in texts
        assert "Text 4" in texts

    def test_pptx_with_notes_extracts_notes(self, sample_files_normal: Path):
        from pptx import Presentation
        pptx_path = sample_files_normal / "with_notes.pptx"
        prs = Presentation(pptx_path)
        notes_found = False
        for slide in prs.slides:
            notes_slide = slide.notes_slide
            if notes_slide and notes_slide.notes_text_frame:
                notes_text = notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    assert "Speaker notes here" in notes_text
                    notes_found = True
        assert notes_found, "Should have found notes in one of the slides"

    def test_pptx_single_slide_extracts_text(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "single_slide.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        texts = [p.text for p in result.paragraphs]
        assert "Single Slide" in texts

    def test_pptx_textbox_extracts_content(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "textbox.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        texts = [p.text for p in result.paragraphs]
        assert "Text Box Content" in texts

    def test_pptx_grouped_shapes_flattened(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "grouped.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        texts = [p.text for p in result.paragraphs]
        assert "Shape 1" in texts
        assert "Shape 2" in texts

    def test_pptx_blank_slide_no_crash(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "blank_slide.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        assert isinstance(result, ExtractionResult)
        assert len(result.paragraphs) == 0

    def test_pptx_empty_notes_handled(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "empty_notes.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        assert isinstance(result, ExtractionResult)

    def test_pptx_smartart_no_crash(self, sample_files_edge: Path):
        pptx_path = sample_files_edge / "smartart.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        assert isinstance(result, ExtractionResult)


class TestPPTXXLIFFOutput:
    """Test PPTX to XLIFF generation."""

    def test_pptx_normal_xliff_translation_units(self, sample_files_normal: Path, tmp_path: Path):
        pptx_path = sample_files_normal / "normal.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "normal.xlf"
        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="fr")

        assert output_xlf.exists()
        content = output_xlf.read_bytes()
        assert len(content) > 0
        assert b"Text" in content

    def test_pptx_single_slide_xliff(self, sample_files_edge: Path, tmp_path: Path):
        pptx_path = sample_files_edge / "single_slide.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "single.xlf"
        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="zh")

        assert output_xlf.exists()

    def test_pptx_textbox_xliff(self, sample_files_edge: Path, tmp_path: Path):
        pptx_path = sample_files_edge / "textbox.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "textbox.xlf"
        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="de")

        assert output_xlf.exists()

    def test_pptx_grouped_xliff_units(self, sample_files_edge: Path, tmp_path: Path):
        pptx_path = sample_files_edge / "grouped.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "grouped.xlf"
        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="es")

        assert output_xlf.exists()


class TestPPTXBothOutput:
    """Test PPTX to both Markdown and XLIFF generation."""

    def test_pptx_xlf_only_creates_file(self, sample_files_normal: Path, tmp_path: Path):
        pptx_path = sample_files_normal / "normal.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "output.xlf"

        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="fr")

        assert output_xlf.exists(), "XLIFF file should be created"

    def test_pptx_edge_case_xlf_output(self, sample_files_edge: Path, tmp_path: Path):
        pptx_path = sample_files_edge / "single_slide.pptx"
        extractor = PPTXExtractor()
        result = extractor.extract(pptx_path)

        output_xlf = tmp_path / "single_out.xlf"

        pipeline = OPPPipeline(tmp_path / "resources")
        pipeline.generate_xliff(result, output_xlf, source_lang="en", target_lang="ja")

        assert output_xlf.exists()


class TestPPTXPipelineIntegration:
    """Test PPTX through full OPP pipeline."""

    def test_pipeline_process_pptx_produces_result(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "normal.pptx")

        assert result.format_type.value == "pptx"
        assert result.content is not None

    def test_pipeline_process_pptx_with_notes(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_notes.pptx")

        assert result.format_type.value == "pptx"
        assert result.content is not None
        assert len(result.errors) == 0

    def test_pipeline_batch_pptx_files(self, sample_files_normal: Path, sample_files_edge: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        files = [
            sample_files_normal / "normal.pptx",
            sample_files_normal / "with_notes.pptx",
            sample_files_edge / "single_slide.pptx",
        ]
        batch_result = pipeline.process_batch(files)

        assert batch_result.successful >= 2
        assert len(batch_result.results) == 3