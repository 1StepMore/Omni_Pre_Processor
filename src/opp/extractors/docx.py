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


def _parse_position_value(pos_elem) -> int:
    """Read a numeric offset from a wp:positionH/wp:positionV element.

    Prefers <wp:posOffset> (EMU integer text), falls back to 0. wp:align
    values are alignment keywords (left/center/right/top/bottom) which are
    not numeric offsets, so they are treated as 0 here; ORF can resolve
    the alignment relative to the page at injection time.
    """
    if pos_elem is None:
        return 0
    offset = pos_elem.find(f'{{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}}posOffset')
    if offset is not None and offset.text:
        try:
            return int(offset.text.strip())
        except (ValueError, TypeError):
            return 0
    return 0


def _extract_anchor_offsets(drawing, WP_NS: str, ns_map: dict) -> tuple[int, int]:
    """Extract (horizontal, vertical) EMU offsets from a wp:anchor.

    Returns (0, 0) for inline drawings or when positionH/positionV is absent.
    """
    anchor = drawing.find(f'.//{WP_NS}anchor', ns_map)
    if anchor is None:
        return (0, 0)
    pos_h = anchor.find(f'{WP_NS}positionH')
    pos_v = anchor.find(f'{WP_NS}positionV')
    return (_parse_position_value(pos_h), _parse_position_value(pos_v))


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
        W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for para in doc.paragraphs:
            # E2E-66 fix: python-docx para.text truncates long paragraphs (only reads
            # first ~35 w:r elements, missing content in paragraphs with 100+ w:t nodes).
            # Use lxml body.findall to read ALL w:t elements for complete text.
            full_text = "".join(
                t.text or "" for t in para._element.findall(f".//{W_NS}t")
            ).strip()
            if not full_text:
                continue
            text = full_text
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
        """Extract w:drawing images from word/document.xml.

        Deduplicates mc:Choice/mc:Fallback renderings (each drawing is
        only counted once even if it has both primary and fallback blips).
        Gets the real paragraph position by walking up the XML tree to
        find the enclosing w:p element. Distinguishes wp:inline from
        wp:anchor (floating) drawings.
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
        R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
        WP_NS = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        MC_NS = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
        ns_map = {'w': W_NS, 'wp': WP_NS}

        try:
            tree = etree.fromstring(document_xml)
        except etree.XMLSyntaxError:
            return result

        body = tree.find(f'{W_NS}body')
        if body is None:
            return result

        all_paragraphs = tree.findall(f'.//{W_NS}p')
        para_to_idx = {p: i for i, p in enumerate(all_paragraphs)}

        for drawing in tree.findall(f'.//{W_NS}drawing'):
            parent = drawing.getparent()
            if parent is not None and parent.tag == f'{MC_NS}Fallback':
                continue

            p = None
            if parent is not None and parent.tag == f'{W_NS}p':
                p = parent
            elif parent is not None:
                p = parent
                while p is not None and p.tag != f'{W_NS}p':
                    p = p.getparent()

            if p is not None and p in para_to_idx:
                para_idx = para_to_idx[p]
            else:
                para_idx = None

            is_floating = drawing.find(f'.//{WP_NS}anchor', ns_map) is not None
            assigned_index = None if is_floating else para_idx
            anchor_h, anchor_v = _extract_anchor_offsets(drawing, WP_NS, ns_map)

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
                            paragraph_index=assigned_index,
                            is_floating=is_floating,
                            wp_anchor_h=anchor_h,
                            wp_anchor_v=anchor_v,
                        ))
                        break
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
        W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        runs = []
        for run in para.runs:
            # E2E-66 fix: use findall to read ALL w:t elements in this run,
            # not just run.text which truncates at ~35 w:r elements.
            # For runs in paragraphs with 100+ w:t nodes, run.text is incomplete.
            run_text = "".join(t.text or "" for t in run._element.findall(f".//{W_NS}t"))
            if not run_text or not run_text.strip():
                continue
            text = run_text

            run_data = RunData(
                text=text,
                bold=bool(run.bold) if run.bold else False,
                italic=bool(run.italic) if run.italic else False,
                underline=bool(run.underline) if run.underline else False,
                strike=bool(run.font.strike) if run.font.strike else False,
            )
            runs.append(run_data)

        return runs
