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
        images = self.extract_images(doc, input_path)

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

    def _extract_inline_drawings(self, doc: DocxDocument, input_path: Path) -> List[ImageData]:
        """Extract inline w:drawing images from word/document.xml.

        These are images embedded directly in paragraph XML via wp:inline or wp:anchor
        elements containing a:blip references to image relationships.
        """
        result: List[ImageData] = []
        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                if 'word/document.xml' not in zf.namelist():
                    return result
                document_xml = zf.read('word/document.xml')
        except zipfile.BadZipFile:
            return result

        try:
            tree = etree.fromstring(document_xml)
        except etree.XMLSyntaxError:
            return result

        # Namespace map for OOXML
        nsmap = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        }

        # Find all w:drawing elements
        for drawing in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
            # Find a:blip elements within the drawing
            for blip in drawing.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
                embed_attr = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if not embed_attr:
                    continue
                # Look up the relationship
                try:
                    rel = doc.part.rels.get(embed_attr)
                    if rel and "image" in rel.target_ref:
                        image_part = rel.target_part
                        image_bytes = image_part.blob
                        content_type = image_part.content_type
                        result.append(ImageData(
                            data=image_bytes,
                            mime_type=content_type,
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

    def extract_images(self, doc: DocxDocument, input_path: Optional[Path] = None) -> List[ImageData]:
        result: List[ImageData] = []
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_part = rel.target_part
                    image_bytes = image_part.blob
                    content_type = image_part.content_type
                    result.append(ImageData(
                        data=image_bytes,
                        mime_type=content_type,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to extract image from DOCX: {e}")

        if input_path:
            inline_images = self._extract_inline_drawings(doc, input_path)
            result.extend(inline_images)

        return result

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
