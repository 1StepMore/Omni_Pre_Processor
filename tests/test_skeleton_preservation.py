import io
import zipfile
from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation

from opp.extractors.docx import DOCXExtractor
from opp.extractors.pptx import PPTXExtractor
from opp.pipeline import OPPPipeline


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
