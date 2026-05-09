from pathlib import Path

import pytest

from opp.extractors.pptx import PPTXExtractor
from opp.utils.exceptions import CorruptedFileError


class TestPPTXExtractor:
    def test_extract_slides_normal(self, sample_files_normal: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_normal / "normal.pptx")
        assert len(result.paragraphs) == 4

    def test_extract_slides_single(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "single_slide.pptx")
        assert len(result.paragraphs) == 1

    def test_extract_slides_blank(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "blank_slide.pptx")
        assert len(result.paragraphs) == 0

    def test_extract_shapes_textbox(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "textbox.pptx")
        assert len(result.paragraphs) >= 1
        assert result.paragraphs[0].text == "Text Box Content"

    def test_extract_shapes_smartart(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "smartart.pptx")
        assert isinstance(result.paragraphs, list)

    def test_extract_shapes_grouped(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "grouped.pptx")
        assert len(result.paragraphs) >= 2

    def test_extract_notes_normal(self, sample_files_normal: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_normal / "with_notes.pptx")
        assert isinstance(result.warnings, list)

    def test_extract_notes_empty(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "empty_notes.pptx")
        assert result.warnings is not None

    def test_extract_notes_long(self, sample_files_edge: Path):
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_edge / "long_notes.pptx")
        assert isinstance(result.paragraphs, list)

    def test_extract_corrupted(self, sample_files_error: Path):
        extractor = PPTXExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "corrupted.pptx")

    def test_supported_extensions(self):
        extractor = PPTXExtractor()
        assert extractor.supported_extensions() == [".pptx"]