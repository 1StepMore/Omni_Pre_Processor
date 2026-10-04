import io
import zipfile
from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation

from opp.extractors.docx import DOCXExtractor
from opp.extractors.html import HTMLExtractor
from opp.extractors.pptx import PPTXExtractor
from opp.pipeline import OPPPipeline
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult


class TestSkeletonPreservation:
    def test_docx_extractor_preserves_skeleton(self, sample_files_normal: Path):
        """Verify DOCX extractor returns skeleton bytes and skeleton_files list."""
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "normal.docx")

        assert result.skeleton is not None, "DOCX skeleton should not be None"
        assert isinstance(result.skeleton, bytes), "DOCX skeleton should be bytes"
        assert len(result.skeleton) > 0, "DOCX skeleton should not be empty"

        assert result.skeleton_files is not None, "DOCX skeleton_files should not be None"
        assert isinstance(result.skeleton_files, list), "DOCX skeleton_files should be a list"
        assert len(result.skeleton_files) > 0, "DOCX skeleton_files should not be empty"
        assert "word/document.xml" in result.skeleton_files, "word/document.xml should be in skeleton_files"

    def test_pptx_extractor_preserves_skeleton(self, sample_files_normal: Path):
        """Verify PPTX extractor returns skeleton bytes and skeleton_files list."""
        extractor = PPTXExtractor()
        result = extractor.extract(sample_files_normal / "normal.pptx")

        assert result.skeleton is not None, "PPTX skeleton should not be None"
        assert isinstance(result.skeleton, bytes), "PPTX skeleton should be bytes"
        assert len(result.skeleton) > 0, "PPTX skeleton should not be empty"

        assert result.skeleton_files is not None, "PPTX skeleton_files should not be None"
        assert isinstance(result.skeleton_files, list), "PPTX skeleton_files should be a list"
        assert len(result.skeleton_files) > 0, "PPTX skeleton_files should not be empty"
        assert any(f.startswith("ppt/") for f in result.skeleton_files), "PPTX skeleton_files should contain ppt/ paths"

    def test_skeleton_zip_is_valid(self, sample_files_normal: Path):
        """Verify the skeleton bytes can be opened as a valid ZIP file."""
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "normal.docx")

        zf = zipfile.ZipFile(io.BytesIO(result.skeleton), 'r')
        try:
            assert zf.testzip() is None, "ZIP file should be valid with no bad entries"
        finally:
            zf.close()

    def test_skeleton_contains_document_xml(self, sample_files_normal: Path):
        """Verify skeleton ZIP contains word/document.xml for DOCX."""
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "normal.docx")

        zf = zipfile.ZipFile(io.BytesIO(result.skeleton), 'r')
        try:
            namelist = zf.namelist()
            assert "word/document.xml" in namelist, "Skeleton ZIP should contain word/document.xml"
        finally:
            zf.close()

    def test_invalid_doc_no_skeleton(self, sample_files_error: Path):
        """Verify invalid files raise CorruptedFileError."""
        from opp.extractors.docx import DOCXExtractor
        from opp.utils.exceptions import CorruptedFileError

        extractor = DOCXExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "corrupted.docx")

    def test_pipeline_save_skeleton(self, tmp_path: Path):
        """Verify OPPPipeline.save_skeleton() writes file correctly."""
        from opp.utils.dataclasses import ExtractionResult, DocumentMetadata, ParagraphData

        doc = Document()
        doc.add_paragraph("Test content")
        test_docx_path = tmp_path / "test.docx"
        doc.save(str(test_docx_path))

        extractor = DOCXExtractor()
        result = extractor.extract(test_docx_path)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        skeleton_path = pipeline.save_skeleton(result, "test", output_dir)

        assert skeleton_path is not None, "save_skeleton should return a path"
        assert skeleton_path.exists(), "Skeleton file should exist"
        assert skeleton_path.name == "test.skeleton.zip", "Skeleton file should have correct name"

        saved_content = skeleton_path.read_bytes()
        assert saved_content == result.skeleton, "Saved skeleton should match original"


HTML_SKELETON_ENTRY = "index.html"

HTML_FIXTURE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Skeleton</title></head>
<body><h1>Main Title</h1><p>Hello World</p><p>Second paragraph</p></body></html>"""


class TestHtmlSkeletonZip:
    """HTML skeletons are packaged as a ZIP so the XLIFF channel stops skipping
    HTML cells (1StepMore/Omni_Pre_Processor#92)."""

    @staticmethod
    def _extract_html(tmp_path: Path) -> ExtractionResult:
        html_file = tmp_path / "test.html"
        html_file.write_text(HTML_FIXTURE, encoding="utf-8")
        result = HTMLExtractor().extract(html_file)
        assert result.skeleton_html is not None
        assert result.skeleton is None, "HTML has no container to rewrite"
        return result

    def test_html_writes_skeleton_zip_on_disk(self, tmp_path: Path):
        result = self._extract_html(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        skeleton_path = pipeline.save_skeleton(result, "test", output_dir)

        assert skeleton_path is not None, "save_skeleton should return a path for HTML"
        assert skeleton_path.name == "test.skeleton.zip"
        assert skeleton_path.exists(), "Skeleton ZIP should exist on disk"
        assert skeleton_path.stat().st_size > 0, "Skeleton ZIP should not be empty"

        with zipfile.ZipFile(skeleton_path) as zf:
            assert zf.testzip() is None, "Skeleton ZIP should be readable"
            assert zf.namelist() == [HTML_SKELETON_ENTRY]
            assert zf.read(HTML_SKELETON_ENTRY).decode("utf-8") == result.skeleton_html

    def test_html_skeleton_entry_is_detectable_as_html(self, tmp_path: Path):
        """ORF's FormatDetector.detect_from_skeleton reports HTML only for a
        top-level .html/.htm entry (no "/" in the name)."""
        result = self._extract_html(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        skeleton_path = pipeline.save_skeleton(result, "test", output_dir)

        with zipfile.ZipFile(skeleton_path) as zf:
            names = zf.namelist()
        assert any(
            n.lower().endswith((".html", ".htm")) and "/" not in n for n in names
        ), f"ORF cannot detect HTML from {names}"
        assert "word/document.xml" not in names
        assert "ppt/presentation.xml" not in names
        assert "xl/workbook.xml" not in names

    def test_html_skeleton_keeps_segment_ids(self, tmp_path: Path):
        result = self._extract_html(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        skeleton_path = pipeline.save_skeleton(result, "test", output_dir)

        with zipfile.ZipFile(skeleton_path) as zf:
            packed = zf.read(HTML_SKELETON_ENTRY).decode("utf-8")
        assert 'data-trans-unit-id="para-' in packed

    def test_non_html_skeleton_html_does_not_write_zip(self, tmp_path: Path):
        """PDF sets skeleton_html too (pdf2html.py) but must stay skeleton-free."""
        result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type="pdf"),
            skeleton_html="<html><body><p>pdf</p></body></html>",
        )
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        assert pipeline.save_skeleton(result, "test", output_dir) is None
        assert not list(output_dir.glob("*.skeleton.zip"))

    def test_html_without_skeleton_html_writes_nothing(self, tmp_path: Path):
        """An HTML page with no matchable block yields skeleton_html=None."""
        html_file = tmp_path / "empty.html"
        html_file.write_text(
            "<!DOCTYPE html><html><head><title>Empty</title></head><body></body></html>",
            encoding="utf-8",
        )
        result = HTMLExtractor().extract(html_file)
        assert result.skeleton_html is None

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        assert pipeline.save_skeleton(result, "empty", output_dir) is None
        assert not list(output_dir.glob("*.skeleton.zip"))
