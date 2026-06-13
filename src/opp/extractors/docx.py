from dataclasses import replace
from pathlib import Path
from typing import List, Optional

import logging
import re
import zipfile
from lxml import etree

import docx
from docx.document import Document as DocxDocument
from docx.table import Table as DocxTable

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
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
    def supported_extensions(self) -> list[str]:
        return [".docx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            doc: DocxDocument = docx.Document(str(input_path))
        except Exception as e:
            if "password" in str(e).lower():
                raise PasswordProtectedError(f"文件受密码保护: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

        # Build element → python-docx object lookups for fast access
        doc_para_lookup = {}
        for p in doc.paragraphs:
            if p._element is not None:
                doc_para_lookup[p._element] = p

        doc_tbl_lookup = {}
        for t in doc.tables:
            if t._tbl is not None:
                doc_tbl_lookup[t._tbl] = t

        paragraphs: list[ParagraphData] = []
        tables: list[TableData] = []
        position = 0

        body_children = list(doc.element.body)
        p_body_index = 0  # sequential counter for w:p elements among body children

        for child in body_children:
            if child.tag == f"{W_NS}p":
                para = doc_para_lookup.get(child)
                if para is None:
                    p_body_index += 1
                    continue

                full_text = "".join(
                    t.text or ""
                    for t in child.iter(f"{W_NS}t")
                    if not any(anc.tag == f"{W_NS}txbxContent" for anc in t.iterancestors())
                ).strip()
                if not full_text:
                    p_body_index += 1
                    continue

                text = full_text
                style_name = para.style.name if para.style else None
                level = None

                if style_name and style_name.startswith("Heading"):
                    try:
                        level = int(style_name.replace("Heading ", "").replace("Heading", ""))
                    except ValueError:
                        level = 1
                elif style_name == "Title":
                    level = 1
                elif style_name == "Subtitle":
                    level = 2

                if level is None and self._is_chinese_heading(text):
                    level = self._detect_chinese_heading_level(text)

                runs = self.extract_runs(para)
                para_idx_in_body = p_body_index
                p_body_index += 1

                paragraphs.append(ParagraphData(
                    text=text,
                    style=style_name,
                    level=level,
                    runs=runs,
                    position=position,
                    para_index_in_body=para_idx_in_body,
                ))
                position += 1

            elif child.tag == f"{W_NS}tbl":
                tbl = doc_tbl_lookup.get(child)
                if tbl is None:
                    continue
                table_data = self._parse_table(tbl, position=position)
                if table_data.headers or table_data.rows:
                    tables.append(table_data)
                    position += 1

        # Append text box paragraphs (tagged with [TextBox] style)
        for p_elem, text in self._walk_textbox_paragraphs(doc.element.body, W_NS):
            paragraphs.append(ParagraphData(
                text=text,
                runs=[],
                style="[TextBox]",
                position=position,
                para_index_in_body=None,
            ))
            position += 1

        para_index_map = self._build_paragraph_index_map(doc)
        images = self.extract_images(doc, input_path, para_index_map)

        skeleton_bytes: bytes | None = None
        skeleton_files: list[str] | None = None
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

    def extract_paragraphs(self, doc: DocxDocument) -> list[ParagraphData]:
        result: list[ParagraphData] = []
        position = 0
        W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        body_children = list(doc.element.body)
        for para in doc.paragraphs:
            # E2E-66 fix: python-docx para.text truncates long paragraphs (only reads
            # first ~35 w:r elements, missing content in paragraphs with 100+ w:t nodes).
            # Use lxml body.findall to read ALL w:t elements for complete text.
            # D.2 fix: skip w:t that lives inside w:txbxContent (textbox/shape content);
            # those are extracted separately by _walk_textbox_paragraphs and would
            # otherwise contaminate the body paragraph's text.
            full_text = "".join(
                t.text or ""
                for t in para._element.iter(f"{W_NS}t")
                if not any(anc.tag == f"{W_NS}txbxContent" for anc in t.iterancestors())
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

            try:
                p_elements = [c for c in body_children if c.tag == f"{{{W_NS}}}p"]
                para_idx_in_body = p_elements.index(para._element)
            except ValueError:
                para_idx_in_body = None

            result.append(ParagraphData(
                text=text,
                style=style_name,
                level=level,
                runs=runs,
                position=position,
                para_index_in_body=para_idx_in_body,
            ))
            position += 1

        for p_elem, text in self._walk_textbox_paragraphs(doc.element.body, W_NS):
            result.append(ParagraphData(
                text=text,
                runs=[],
                position=position,
                para_index_in_body=None,
            ))
            position += 1
        return result

    def _walk_textbox_paragraphs(self, body_elem, W_NS: str):
        """Yield (w:p element, text) for each non-empty w:p inside w:txbxContent.

        Body-level doc.paragraphs excludes textbox paragraphs (which live in
        w:drawing/w:txbxContent or w:pict/w:txbxContent). Deduplicates by text
        content because mc:AlternateContent often holds the same textbox in
        both mc:Choice and mc:Fallback.
        """
        txbx_tag = f"{W_NS}txbxContent"
        p_tag = f"{W_NS}p"
        t_tag = f"{W_NS}t"
        seen: set[str] = set()
        for txbx in body_elem.iter(txbx_tag):
            for p_elem in txbx.iter(p_tag):
                text = "".join((t.text or "") for t in p_elem.iter(t_tag)).strip()
                if text and text not in seen:
                    seen.add(text)
                    yield p_elem, text

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

    def extract_tables(self, doc: DocxDocument) -> list[TableData]:
        result: list[TableData] = []
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
    ) -> list[ImageData]:
        """Extract w:drawing images from word/document.xml.

        Uses lxml DOM parsing (``fromstring`` + ``iter()``) instead of
        streaming ``iterparse``.  The previous iterparse-implementation
        suffered from a destructive-clear bug: ``elem.clear()`` in the
        ``finally`` block cleared ``a:blip`` descendant element
        *attributes* before the parent ``w:drawing`` end-event fired,
        making ``blip.get(embed_attr)`` always return ``None``.

        This approach parses the full XML into memory (safe for typical
        office documents; even a dense 6.7 MB document.xml peaks at
        ~40 MB DOM) and walks the tree cleanly.

        Paragraph assignment: only direct children of ``w:body`` count
        as body paragraphs.  Drawings inside ``w:txbxContent`` (text
        boxes) or ``w:tc`` (table cells) get ``paragraph_index=None``
        because they are not body-level paragraphs.

        Deduplicates mc:AlternateContent renderings: when the same
        ``w:p`` contains both a direct ``w:drawing`` and an
        ``mc:Choice`` variant with the same relationship ID, only
        the first occurrence (document order) is extracted.

        Distinguishes ``wp:inline`` from ``wp:anchor`` (floating)
        drawings.  Floating drawings always get ``paragraph_index=None``
        since they are not anchored to a text flow position.
        """
        result: list[ImageData] = []

        W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
        R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
        WP_NS = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        ns_map = {'w': W_NS, 'wp': WP_NS}
        body_tag = f'{W_NS}body'
        p_tag = f'{W_NS}p'
        drawing_tag = f'{W_NS}drawing'
        t_tag = f'{W_NS}t'

        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                if 'word/document.xml' not in zf.namelist():
                    return result
                doc_xml_bytes = zf.read('word/document.xml')
        except (zipfile.BadZipFile, KeyError) as e:
            logger.warning(f"Cannot read document.xml for image extraction: {e}")
            return result

        try:
            tree = etree.fromstring(doc_xml_bytes)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Cannot parse document.xml for image extraction: {e}")
            return result

        # Locate the <w:body> element (root is <w:document> which contains <w:body>).
        body = tree if tree.tag == body_tag else tree.find(body_tag)
        if body is None:
            logger.warning("No <w:body> found in document.xml — cannot extract drawings")
            return result

        # Build position mapping from body-level paragraphs only.
        # Uses body-child index (via body.index()) as stable key: lxml recycles
        # Element proxy objects during iteration, so Python id() is unreliable.
        # body.index() compares C-level xmlNode pointers and works across
        # separate lxml proxies for the same XML node.
        p_positions: dict[int, int] = {}
        for child_idx, child in enumerate(body):
            if child.tag == p_tag:
                text_content = "".join(
                    t.text or "" for t in child.iter(t_tag)
                ).strip()
                if text_content:
                    p_positions[child_idx] = len(p_positions)

        # Track seen relationship-IDs per paragraph for AlternateContent dedup.
        # Uses XPath path (via ElementTree.getpath()) as stable paragraph key:
        # `body.index()` only works for body-level children, but paragraphs
        # inside text boxes or table cells need a unique identifier too.
        # `getpath()` returns an XPath like "/w:document/w:body/w:p[7]" which
        # is unique across the entire document and stable across lxml proxies.
        MC_NS = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
        alt_content_tag = f'{MC_NS}AlternateContent'
        et_element_tree = etree.ElementTree(tree)
        seen_r_ids: set[tuple[str, str]] = set()

        def _is_alternate_content_drawing(elem):
            """Check if a drawing element is inside mc:AlternateContent."""
            parent = elem.getparent()
            while parent is not None:
                if parent.tag == alt_content_tag:
                    return True
                parent = parent.getparent()
            return False

        for drawing_elem in tree.iter(drawing_tag):
            # Walk up to find the enclosing w:p.
            p_elem = drawing_elem.getparent()
            while p_elem is not None and p_elem.tag != p_tag:
                p_elem = p_elem.getparent()
            if p_elem is None:
                continue

            # Unique paragraph path for dedup.
            try:
                p_path = et_element_tree.getpath(p_elem)
            except Exception:
                p_path = None

            # Body-level check: does this w:p live directly under w:body?
            is_body_level = (
                p_elem.getparent() is not None
                and p_elem.getparent().tag == body_tag
            )
            para_idx = None
            child_idx = None
            if is_body_level:
                # body.index() compares C-level xmlNode — reliable across proxies.
                try:
                    child_idx = body.index(p_elem)
                    para_idx = p_positions.get(child_idx)
                except ValueError:
                    pass

            is_floating = drawing_elem.find(f'.//{WP_NS}anchor', ns_map) is not None
            assigned_index = None if is_floating else para_idx
            anchor_h, anchor_v = _extract_anchor_offsets(drawing_elem, WP_NS, ns_map)

            # Extract wp:extent cx/cy (already in EMU) for width/height.
            # Both wp:inline and wp:anchor drawings carry <wp:extent cx cy/>.
            extent = drawing_elem.find(f'.//{WP_NS}extent', ns_map)
            cx = extent.get('cx') if extent is not None else None
            cy = extent.get('cy') if extent is not None else None
            img_width = int(cx) if cx is not None else None
            img_height = int(cy) if cy is not None else None

            for blip in drawing_elem.iter(f'{A_NS}blip'):
                embed_attr = blip.get(f'{R_NS}embed')
                if not embed_attr:
                    continue

                # Dedup: only for mc:AlternateContent pairs (Choice+Fallback)
                # that reference the same image rId.  Separate legitimate
                # drawings in the same paragraph are NOT deduplicated even
                # if they share an rId (e.g. repeated logo in a paragraph).
                if _is_alternate_content_drawing(drawing_elem):
                    dedup_key = (p_path, embed_attr)
                    if dedup_key in seen_r_ids:
                        continue
                    seen_r_ids.add(dedup_key)

                try:
                    rel = doc.part.rels.get(embed_attr)
                    if rel and "image" in rel.reltype:
                        image_part = rel.target_part
                        img_bytes = image_part.blob
                        mime = image_part.content_type
                        img_kwargs = {
                            "mime_type": mime,
                            "paragraph_index": assigned_index,
                            "is_floating": is_floating,
                            "wp_anchor_h": anchor_h,
                            "wp_anchor_v": anchor_v,
                            "width": img_width,
                            "height": img_height,
                        }
                        if len(img_bytes) > 100 * 1024:
                            ext = mime.split("/")[-1] if "/" in mime else "bin"
                            temp_dir = Path(input_path).parent / f"{Path(input_path).stem}_images"
                            temp_dir.mkdir(parents=True, exist_ok=True)
                            temp_path = temp_dir / f"image_{len(result)}.{ext}"
                            temp_path.write_bytes(img_bytes)
                            result.append(ImageData(
                                data=b"",
                                temp_path=temp_path,
                                **img_kwargs,
                            ))
                        else:
                            result.append(ImageData(
                                data=img_bytes,
                                **img_kwargs,
                            ))
                        break
                except Exception as e:
                    logger.warning(
                        f"Failed to extract inline drawing image: {e}"
                    )

        return result

    def _parse_table(self, table: DocxTable, position: int = 0) -> TableData:
        headers: list[str] = []
        rows: list[list[str]] = []

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
                    p_elements = [c for c in body if c.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"]
                    para_index_map[id(para._element)] = p_elements.index(para._element)
                except ValueError:
                    para_index_map[id(para._element)] = pos
                pos += 1
        return para_index_map

    def extract_images(
        self,
        doc: DocxDocument,
        input_path: Path | None = None,
        para_index_map: dict | None = None,
    ) -> list[ImageData]:
        if input_path and para_index_map is not None:
            return self._extract_inline_drawings(doc, input_path, para_index_map)
        return []

    def extract_runs(self, para) -> list[RunData]:
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

            font_size_hp = None
            if run.font.size is not None:
                font_size_hp = int(run.font.size.pt * 2)
            color_hex = None
            if run.font.color.rgb is not None:
                color_hex = str(run.font.color.rgb)
            run_data = RunData(
                text=text,
                bold=bool(run.bold) if run.bold else False,
                italic=bool(run.italic) if run.italic else False,
                underline=bool(run.underline) if run.underline else False,
                strike=bool(run.font.strike) if run.font.strike else False,
                font_size=font_size_hp,
                font_name=run.font.name,
                color=color_hex,
            )
            runs.append(run_data)

        return runs
