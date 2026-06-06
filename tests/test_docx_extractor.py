from pathlib import Path

import pytest

from opp.extractors.docx import DOCXExtractor
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class TestDOCXExtractor:
    def test_extract_paragraphs_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "normal.docx")
        assert len(result.paragraphs) == 3
        assert result.paragraphs[0].text == "Heading 1"
        assert result.paragraphs[0].level == 1
        assert result.paragraphs[1].style == "Normal"

    def test_extract_paragraphs_empty(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "empty.docx")
        assert len(result.paragraphs) == 0
        assert "文档为空" in result.warnings

    def test_extract_paragraphs_single(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "single_para.docx")
        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].text == "Single Paragraph"

    def test_extract_tables_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_table.docx")
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["Header1", "Header2"]
        assert len(result.tables[0].rows) == 2

    def test_extract_tables_nested(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "nested_table.docx")
        assert len(result.tables) >= 2

    def test_extract_images_normal(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_image.docx")
        assert hasattr(result, 'images')

    def test_extract_images_single(self, sample_files_edge: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_edge / "single_image.docx")
        assert hasattr(result, 'images')

    def test_extract_corrupted(self, sample_files_error: Path):
        extractor = DOCXExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(sample_files_error / "corrupted.docx")

    def test_extract_password_protected(self, sample_files_error: Path):
        extractor = DOCXExtractor()
        with pytest.raises((CorruptedFileError, FileNotFoundError)):
            extractor.extract(sample_files_error / "nonexistent.docx")

    def test_supported_extensions(self):
        extractor = DOCXExtractor()
        assert extractor.supported_extensions() == [".docx"]

    def test_table_cell_paragraphs_are_extracted(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_table.docx")
        para_texts = [p.text for p in result.paragraphs]
        for cell_text in ("Header1", "Header2", "Row1Cell1", "Row1Cell2", "Row2Cell1", "Row2Cell2"):
            assert cell_text in para_texts, f"Table cell text {cell_text!r} missing from result.paragraphs"

    def test_table_cell_paragraphs_have_none_para_index_in_body(self, sample_files_normal: Path):
        extractor = DOCXExtractor()
        result = extractor.extract(sample_files_normal / "with_table.docx")
        cell_paras = [p for p in result.paragraphs if p.text in {"Header1", "Header2", "Row1Cell1", "Row1Cell2", "Row2Cell1", "Row2Cell2"}]
        assert len(cell_paras) == 6
        for p in cell_paras:
            assert p.para_index_in_body is None, f"{p.text!r} should have para_index_in_body=None"

    def test_textbox_paragraphs_are_extracted(self, tmp_path: Path):
        """D.2: paragraphs inside w:txbxContent (textboxes) are extracted."""
        from docx import Document
        from lxml import etree as _etree
        doc = Document()
        p = doc.add_paragraph("Body para before")
        txbx_xml = """<w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:p><w:r><w:t>TextBox Chinese 文本框</w:t></w:r></w:p>
        </w:txbxContent>"""
        p._element.append(_etree.fromstring(txbx_xml))
        doc.add_paragraph("Body para after")
        path = tmp_path / "with_textbox.docx"
        doc.save(str(path))
        extractor = DOCXExtractor()
        result = extractor.extract(path)
        para_texts = [p.text for p in result.paragraphs]
        assert "Body para before" in para_texts
        assert "Body para after" in para_texts
        assert "TextBox Chinese 文本框" in para_texts

    def test_textbox_dedup_mc_alternate_content(self, tmp_path: Path):
        """D.2: same textbox paragraph inside mc:Choice and mc:Fallback appears only once."""
        from docx import Document
        from lxml import etree as _etree
        doc = Document()
        p = doc.add_paragraph("Body para")
        alt_xml = """<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                           xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                           xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                           xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
                           xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
            <mc:AlternateContent>
                <mc:Choice Requires="wps">
                    <w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
                        <wp:extent cx="600000" cy="600000"/>
                        <wp:docPr id="1" name="TB"/>
                        <a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
                            <wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="600000" cy="600000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></wps:spPr>
                            <wps:txbx><w:txbxContent><w:p><w:r><w:t>Dedup target 唯一</w:t></w:r></w:p></w:txbxContent></wps:txbx>
                            <wps:bodyPr/>
                        </wps:wsp></a:graphicData></a:graphic>
                    </wp:inline></w:drawing>
                </mc:Choice>
                <mc:Fallback>
                    <w:pict><w:txbxContent><w:p><w:r><w:t>Dedup target 唯一</w:t></w:r></w:p></w:txbxContent></w:pict>
                </mc:Fallback>
            </mc:AlternateContent>
        </w:r>"""
        p._element.append(_etree.fromstring(alt_xml))
        path = tmp_path / "with_dup_textbox.docx"
        doc.save(str(path))
        extractor = DOCXExtractor()
        result = extractor.extract(path)
        matches = [pp for pp in result.paragraphs if pp.text == "Dedup target 唯一"]
        assert len(matches) == 1, f"Expected 1 (deduped), got {len(matches)}"