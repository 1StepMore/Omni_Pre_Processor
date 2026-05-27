from dataclasses import replace
from pathlib import Path
from typing import List, Optional

import logging
import re
import zipfile
from lxml import etree

import docx
import warnings
from docx.document import Document as DocxDocument
from docx.table import Table as DocxTable

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    RunData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError

logger = logging.getLogger(__name__)

# Chinese numbered heading patterns for heuristic detection
CHINESE_NUMERIC = '[零一二三四五六七八九十百千零\\d]+'
CHINESE_HEADING_PATTERNS = [
    re.compile(rf'^第{CHINESE_NUMERIC}[章节条款]'),   # 第X章/节/条
    re.compile(rf'^{CHINESE_NUMERIC}[、.]'),          # X、or X.  
    re.compile(r'^【[^】]+】'),                        # 【标题】
    re.compile(rf'^{CHINESE_NUMERIC}、'),              # 一、二、三、
    re.compile(r'^附录'),                              # 附录
    re.compile(r'^[一二三四五六七八九十]+、'),         # 一、二、三、 (without digits)
]


class DOCXExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".docx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            doc: DocxDocument = docx.Document(str(input_path))
        except Exception as e:
            if "password" in str(e).lower():
                raise PasswordProtectedError(f"文件受密码保护: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        paragraphs = self.extract_paragraphs(doc)
        tables = self.extract_tables(doc)
        para_index_map = self._build_paragraph_index_map(doc)
        images = self.extract_images(doc, input_path, para_index_map)

        skeleton_bytes: Optional[bytes] = None
        skeleton_files: Optional[List[str]] = None
        try:
            with open(input_path, 'rb') as f:
                skeleton_bytes = f.read()
            with zipfile.ZipFile(input_path, 'r') as zf:
                key_files = [
                    'word/document.xml',      # Main document content
                    'word/styles.xml',         # Style definitions
                    'word/numbering.xml',     # Numbering definitions
                    'word/settings.xml',      # Document settings
                    '[Content_Types].xml',   # Content type declarations
                ]
                skeleton_files = [f for f in key_files if f in zf.namelist()]
        except zipfile.BadZipFile:
            warnings.append("Skeleton extraction failed: not a valid ZIP/DOCX file")
            skeleton_bytes = None
            skeleton_files = None

        if not paragraphs and not tables:
            warnings.append("文档为空")

        metadata = replace(metadata, page_count=1)

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
            skeleton=skeleton_bytes,
            skeleton_files=skeleton_files,
        )

    def extract_paragraphs(self, doc: DocxDocument) -> List[ParagraphData]:
        result: List[ParagraphData] = []
        position = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = para.style.name if para.style else None
            level = None

            # Handle "Heading 1", "Heading 2", etc.
            if style_name and style_name.startswith("Heading"):
                try:
                    level = int(style_name.replace("Heading ", "").replace("Heading", ""))
                except ValueError:
                    level = 1
            # Handle "Title" style -> level 1
            elif style_name == "Title":
                level = 1
            # Handle "Subtitle" style -> level 2
            elif style_name == "Subtitle":
                level = 2

            # Heuristic detection for Chinese-numbered headings in text
            if level is None and self._is_chinese_heading(text):
                level = self._detect_chinese_heading_level(text)

            runs = self.extract_runs(para)

            result.append(ParagraphData(
                text=text,
                style=style_name,
                level=level,
                runs=runs,
                position=position,
            ))
            position += 1
        return result

    def _is_chinese_heading(self, text: str) -> bool:
        for pattern in CHINESE_HEADING_PATTERNS:
            if pattern.match(text):
                return True
        return False

    def _detect_chinese_heading_level(self, text: str) -> int:
        # Check more specific patterns first (order matters!)
        # 第X节 -> level 2 (before 第X[章节条款] which would match 节 and return 1)
        if re.match(rf'^第{CHINESE_NUMERIC}节', text):
            return 2
        # 第X章/第X条 or 附录 -> level 1
        if re.match(rf'^第{CHINESE_NUMERIC}[章节条款]|^附录', text):
            return 1
        if re.match(r'^[一二三四五六七八九十零]+、', text):
            return 2
        return 3

    def extract_tables(self, doc: DocxDocument) -> List[TableData]:
        result: List[TableData] = []
        position = 0
        for table in doc.tables:
            table_data = self._parse_table(table, position=position)
            if table_data.headers or table_data.rows:
                result.append(table_data)
            position += 1
        return result

    def _extract_inline_drawings(
        self,
        doc: DocxDocument,
        input_path: Path,
        paragraph_index_map: dict,
    ) -> List[ImageData]:
        """Extract inline w:drawing images from word/document.xml.

        Uses iterparse to walk paragraphs in document order, counting
        non-empty w:p elements. This avoids the id() mismatch between
        python-docx CT_P objects and lxml elements from a separate parse.
        """
        result: List[ImageData] = []
        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                if 'word/document.xml' not in zf.namelist():
                    return result
                document_xml = zf.read('word/document.xml')
        except zipfile.BadZipFile:
            return result

        W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
        T_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

        para_count = 0
        pending_drawings: List[tuple] = []

        try:
            from io import BytesIO
            for event, elem in etree.iterparse(BytesIO(document_xml), events=('end',)):
                if elem.tag == f'{W_NS}p':
                    text = ''.join(t.text or '' for t in elem.iter(f'{T_NS}t'))
                    if text.strip():
                        para_count += 1
                elif elem.tag == f'{W_NS}drawing':
                    pending_drawings.append((para_count, elem))
        except etree.XMLSyntaxError:
            return result

        for drawing_para_index, drawing in pending_drawings:
            for blip in drawing.iter(f'{A_NS}blip'):
                embed_attr = blip.get(f'{R_NS}embed')
                if not embed_attr:
                    continue
                try:
                    rel = doc.part.rels.get(embed_attr)
                    if rel and "image" in rel.reltype:
                        image_part = rel.target_part
                        result.append(ImageData(
                            data=image_part.blob,
                            mime_type=image_part.content_type,
                            paragraph_index=drawing_para_index,
                        ))
                except Exception as e:
                    logger.warning(f"Failed to extract inline drawing image: {e}")

        return result

    def _parse_table(self, table: DocxTable, position: int = 0) -> TableData:
        headers: List[str] = []
        rows: List[List[str]] = []

        if table.rows:
            first_row = table.rows[0]
            headers = [cell.text.strip() for cell in first_row.cells]

            for row in table.rows[1:]:
                rows.append([cell.text.strip() for cell in row.cells])

        return TableData(headers=headers, rows=rows, position=position)

    def _build_paragraph_index_map(self, doc: DocxDocument) -> dict:
        """Build a mapping from w:p element to paragraph index (0-based).

        Uses body.index() on the underlying lxml element so the index is
        stable across separate lxml parses (unlike id() which changes).
        """
        body = doc.element.body
        para_index_map = {}
        pos = 0
        for para in doc.paragraphs:
            if para.text.strip():
                try:
                    para_index_map[id(para._element)] = body.index(para._element)
                except ValueError:
                    para_index_map[id(para._element)] = pos
                pos += 1
        return para_index_map

    def extract_images(
        self,
        doc: DocxDocument,
        input_path: Optional[Path] = None,
        para_index_map: Optional[dict] = None,
    ) -> List[ImageData]:
        if input_path and para_index_map is not None:
            return self._extract_inline_drawings(doc, input_path, para_index_map)
        return []

    def extract_runs(self, para) -> List[RunData]:
        """Extract individual runs with formatting properties from a paragraph.

        Args:
            para: python-docx Paragraph object

        Returns:
            List of RunData with text and formatting
        """
        runs = []
        for run in para.runs:
            text = run.text
            if not text or not text.strip():
                continue

            run_data = RunData(
                text=text,
                bold=bool(run.bold) if run.bold else False,
                italic=bool(run.italic) if run.italic else False,
                underline=bool(run.underline) if run.underline else False,
                strike=bool(run.font.strike) if run.font.strike else False,
            )
            runs.append(run_data)

        return runs
