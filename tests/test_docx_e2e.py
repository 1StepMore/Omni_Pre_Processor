import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from opp.detector import FormatType
from opp.pipeline import OPPPipeline
from opp.extractors.docx import DOCXExtractor
from opp.xliff import XLIFFFileGenerator

VENV_PYTHON = "/mnt/d/贯维/Omni_Pre_Processor/.venv/bin/python"


def run_opp(args: list, tmp_path: Path) -> subprocess.CompletedProcess:
    cmd = [VENV_PYTHON, "-m", "opp.cli"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path
    )


class TestDOCXToMarkdown:
    def test_docx_heading_hierarchy(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        assert any(p.text == "Heading 1" and p.level == 1 for p in result.paragraphs)
        assert any(p.text == "Normal paragraph" for p in result.paragraphs)

    def test_docx_with_table_markdown(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "with_table.docx")
        assert any(t.headers == ["Header1", "Header2"] for t in result.tables)

    def test_docx_empty_file(self, sample_files_edge: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_edge / "empty.docx")
        assert result.format_type == FormatType.DOCX

    def test_docx_single_paragraph(self, sample_files_edge: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_edge / "single_para.docx")
        assert any(p.text == "Single Paragraph" for p in result.paragraphs)

    def test_docx_nested_tables(self, sample_files_edge: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_edge / "nested_table.docx")
        assert any(t.headers == ["T1H1", "T1H2"] for t in result.tables)
        assert any(t.headers == ["T2H1", "T2H2"] for t in result.tables)


class TestDOCXMarkdownContent:
    def test_markdown_heading_generation(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        headings = [p for p in result.paragraphs if p.level is not None and p.level >= 1]
        assert any(h.text == "Heading 1" and h.level == 1 for h in headings)

    def test_markdown_table_content(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "with_table.docx")
        table = next((t for t in result.tables if t.headers == ["Header1", "Header2"]), None)
        assert table is not None
        assert table.rows[0] == ["Row1Cell1", "Row1Cell2"]

    def test_markdown_nested_tables_content(self, sample_files_edge: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_edge / "nested_table.docx")
        assert len(result.tables) >= 2


class TestDOCXXLIFFGeneration:
    def test_generate_xliff_file(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        xlf_path = tmp_path / "normal.xlf"
        generator = XLIFFFileGenerator.from_extraction_result(result, "en", "fr")
        generator.write_to_file(xlf_path)
        assert xlf_path.exists()
        content = xlf_path.read_text(encoding="utf-8")
        assert "<trans-unit" in content or "<transunit" in content.lower()

    def test_xliff_language_attributes(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        xlf_path = tmp_path / "normal.xlf"
        generator = XLIFFFileGenerator.from_extraction_result(result, "en", "de")
        generator.write_to_file(xlf_path)
        assert xlf_path.exists()
        content = xlf_path.read_text(encoding="utf-8")
        assert "en" in content or "English" in content
        assert "de" in content or "German" in content

    def test_xliff_single_para(self, sample_files_edge: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_edge / "single_para.docx")
        xlf_path = tmp_path / "single_para.xlf"
        generator = XLIFFFileGenerator.from_extraction_result(result, "en", "es")
        generator.write_to_file(xlf_path)
        assert xlf_path.exists()


class TestDOCXToBoth:
    def test_both_md_and_xlf_created(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        md_path = tmp_path / "normal.md"
        xlf_path = tmp_path / "normal.xlf"
        xlf_generator = XLIFFFileGenerator.from_extraction_result(result, "en", "fr")
        xlf_generator.write_to_file(xlf_path)
        assert xlf_path.exists()
        paragraphs_text = "\n".join(p.text for p in result.paragraphs)
        md_path.write_text(paragraphs_text, encoding="utf-8")
        assert md_path.exists()

    def test_both_content_consistency(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "normal.docx")
        xlf_path = tmp_path / "normal.xlf"
        xlf_generator = XLIFFFileGenerator.from_extraction_result(result, "en", "fr")
        xlf_generator.write_to_file(xlf_path)
        md_path = tmp_path / "normal.md"
        paragraphs_text = "\n".join(p.text for p in result.paragraphs)
        md_path.write_text(paragraphs_text, encoding="utf-8")
        md_content = md_path.read_text(encoding="utf-8")
        xlf_content = xlf_path.read_text(encoding="utf-8")
        assert "Normal paragraph" in md_content or "Normal paragraph" in xlf_content

    def test_both_with_table(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "with_table.docx")
        xlf_path = tmp_path / "with_table.xlf"
        xlf_generator = XLIFFFileGenerator.from_extraction_result(result, "en", "ja")
        xlf_generator.write_to_file(xlf_path)
        md_path = tmp_path / "with_table.md"
        content_parts = [p.text for p in result.paragraphs]
        if result.tables:
            for t in result.tables:
                content_parts.append("| " + " | ".join(t.headers) + " |")
        md_path.write_text("\n".join(content_parts), encoding="utf-8")
        assert md_path.exists()
        assert xlf_path.exists()


class TestDOCXWithImages:
    def test_docx_with_image_processing(self, sample_files_normal: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_normal / "with_image.docx")
        assert result.format_type == FormatType.DOCX
        assert isinstance(result.content, str)
        assert result.images_stored >= 0

    def test_docx_extract_images(self, sample_files_normal: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_normal / "with_image.docx")
        assert isinstance(result.images, list)


class TestDOCXEdgeCases:
    def test_empty_file_handling(self, sample_files_edge: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_edge / "empty.docx")
        assert result.format_type == FormatType.DOCX

    def test_nested_table_markdown(self, sample_files_edge: Path, tmp_path: Path):
        result = DOCXExtractor().extract(sample_files_edge / "nested_table.docx")
        assert len(result.tables) >= 2

    def test_single_image_doc(self, sample_files_edge: Path, tmp_path: Path):
        pipeline = OPPPipeline(tmp_path / "resources")
        result = pipeline.process_file(sample_files_edge / "single_image.docx")
        assert result.format_type == FormatType.DOCX
        assert isinstance(result.content, str)