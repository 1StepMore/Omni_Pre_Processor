"""HTMLExtractor — HTML document extraction for OPP.

Orchestrates the full extraction pipeline:
  spa detection → readability/docling extraction → markdown conversion
  → paragraph/runs parsing → image extraction → skeleton HTML.

Delegates framework-specific logic to submodules:
  - ``spa_detector`` — SPA/JS-heavy page heuristic detection
  - ``markdown_converter`` — readability/docling → markdownify pipeline
  - ``table_extractor`` — markdown table fixup
"""

import base64
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from opp.config import is_table_paragraph_units_enabled
from opp.extractors.base import ExtractorBase
from opp.extractors.html.markdown_converter import (
    DOCLING_AVAILABLE,
    check_quality,
    extract_text_from_tree,
    extract_with_docling,
    extract_with_readability,
    html_to_markdown,
    resolve_relative_paths,
    strip_scripts_and_styles,
)
from opp.extractors.html.markdown_converter import (
    # 冗余别名：这两个可用性开关同时是**再导出契约**（tests/test_html_extractor_split.py
    # 用 hasattr(html_mod, ...) 断言它们可从本包拿到），显式别名让再导出意图对
    # ruff(F401) 与读者都成立，避免被误当作死导入删掉。
    MARKDOWNIFY_AVAILABLE as MARKDOWNIFY_AVAILABLE,
)
from opp.extractors.html.markdown_converter import (
    READABILITY_AVAILABLE as READABILITY_AVAILABLE,
)
from opp.extractors.html.spa_detector import detect_js_heavy
from opp.extractors.html.table_extractor import _check_table_broken, fix_tables
from opp.logger import logger
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    RunData,
    TableCellData,
)
from opp.utils.exceptions import CorruptedFileError

# ── Module-level regex patterns (used by methods in this module) ───


def _page_number_for(img: Any, page_by_div: dict[Any, int]) -> int | None:
    """1-based page number taken from the enclosing ``div.page`` ancestor.

    ``PDF2HTMLExtractor`` already wraps each page's fragment in
    ``<div class="page">`` before handing the document to this extractor, so the
    page provenance survives the PDF->HTML hop without stamping anything onto
    the ``<img>`` tags themselves. Only PDF-derived documents carry those
    wrappers, so any other HTML input yields ``None`` -- which is what
    ``MarkdownGenerator``'s position fallback chain expects.
    """
    node = img.parent
    while node is not None:
        page = page_by_div.get(node)
        if page is not None:
            return page
        node = node.parent
    return None

_RE_DATA_URI = re.compile(r"data:([^;]+);base64,(.+)$")
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.*)")
_RE_BULLET_LIST = re.compile(r"^[\-\*]\s+")
_RE_ORDERED_LIST = re.compile(r"^\d+\.\s+")
_RE_CODE_FENCE = re.compile(r"^(?:```|~~~)")
_BLOCK_TEXT_TAGS = frozenset(
    {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "td",
        "th",
        "article",
        "section",
        "header",
        "footer",
        "aside",
        "main",
        "nav",
    }
)

# OPP#80 Wave 2 — HTML table-cell block model.  Mirrors the ORF HTML writer's
# ``_HTML_BLOCK_TAGS`` / ``_cell_paragraph_groups`` (xliff2html/writer.py) so
# both sides number a cell's ``_para{p}`` groups identically: a direct-child
# element whose tag is block-level is its own group; a maximal run of
# consecutive non-block direct children (text / ``<br>`` / inline element) is
# one inline group.  Whitespace-only runs still consume a group index so a
# following non-empty group keeps the same ``{p}`` ORF will resolve.  Keep this
# set in sync with ORF (a drift silently misplaces translations).
_TABLE_CELL_BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "section",
        "article",
        "li",
        "blockquote",
        "pre",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "table",
        "figure",
        "figcaption",
        "address",
        "dt",
        "dd",
        "hr",
    }
)

_RE_WHITESPACE_RUN = re.compile(r"\s+")


def _is_table_cell_block(node: Any) -> bool:
    """True for a direct-child ``Tag`` whose tag name is in the block set."""
    return (
        isinstance(node, Tag)
        and isinstance(node.name, str)
        and node.name.lower() in _TABLE_CELL_BLOCK_TAGS
    )


def _table_cell_group_text(group: list[Any]) -> str:
    """Concatenated descendant text of one group, whitespace-collapsed."""
    parts = [
        node.get_text(" ", strip=True) if isinstance(node, Tag) else str(node)
        for node in group
    ]
    return _RE_WHITESPACE_RUN.sub(" ", " ".join(parts)).strip()


def _table_cell_paragraph_groups(cell: Any) -> list[list[Any]]:
    """Enumerate a cell's direct children as paragraph groups, as ORF does.

    Walks the cell's direct children in document order; a block-level child is
    its own group, every other child accumulates into the current inline run,
    flushed when a block child appears and at the end.  Whitespace-only nodes
    are kept, so every following group's index matches ORF's
    ``_cell_paragraph_groups`` exactly.
    """
    groups: list[list[Any]] = []
    inline_run: list[Any] = []
    for child in cell.children:
        if _is_table_cell_block(child):
            if inline_run:
                groups.append(inline_run)
                inline_run = []
            groups.append([child])
        else:
            inline_run.append(child)
    if inline_run:
        groups.append(inline_run)
    return groups


def _table_cell_units(
    cell: Any, table_index: int, row: int, col: int
) -> list[TableCellData]:
    """Build the translatable units for one cell with the flag ON.

    A cell becomes per-paragraph only when it has at least two direct
    block-level children AND no inline group carries non-whitespace text.
    Anything else (inline-only, or a stray ``intro<p>..</p>`` prefix) keeps the
    legacy whole-cell unit.  A whitespace-only group emits no unit but still
    consumes its group index, so a later group's ``para_index`` stays aligned
    with ORF.
    """
    groups = _table_cell_paragraph_groups(cell)
    block_children = sum(
        1 for child in cell.children if _is_table_cell_block(child)
    )
    has_stray_inline = any(
        _table_cell_group_text(group)
        for group in groups
        if not (len(group) == 1 and _is_table_cell_block(group[0]))
    )

    if block_children >= 2 and not has_stray_inline:
        units: list[TableCellData] = []
        for index, group in enumerate(groups):
            text = _table_cell_group_text(group)
            if text:
                units.append(TableCellData(
                    table_index=table_index,
                    row=row,
                    col=col,
                    text=text,
                    para_index=index,
                ))
        return units

    text = cell.get_text(" ", strip=True)
    if not text:
        return []
    return [TableCellData(
        table_index=table_index,
        row=row,
        col=col,
        text=text,
    )]


# ── HTMLExtractor ──────────────────────────────────────────────────


class HTMLExtractor(ExtractorBase):
    """Extract structured content from HTML documents.

    Supports ``.html`` and ``.htm`` files. Uses readability (or
    docling AI) for main content extraction, then converts to
    markdown and parses paragraphs, runs, images, and skeleton.
    """

    # ── Public API ───────────────────────────────────────────────

    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        file_metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            content = input_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = input_path.read_text(encoding="latin-1")
            except Exception:
                logger.debug("Failed to read HTML file with latin-1 fallback: %s", input_path)
                raise CorruptedFileError(f"无法读取HTML文件: {input_path}")

        metadata = DocumentMetadata(
            file_size=file_metadata.file_size,
            format_type="html",
        )

        if self._detect_js_heavy(content):
            warnings.append("JS-rendered page detected")

        tool_choice = self._get_tool_choice()
        logger.info(f"HTML提取: 模式={tool_choice}")

        if tool_choice == "complex":
            if DOCLING_AVAILABLE:
                logger.info("使用docling(AI)提取HTML")
                # E2E-82: fall back to readability if docling fails
                # (raises or returns empty) instead of silently using
                # empty content.
                try:
                    extracted_text = self._extract_with_docling(content)
                except Exception as e:
                    logger.warning(
                        f"docling failed ({type(e).__name__}: {e}), "
                        f"降级到readability"
                    )
                    warnings.append(
                        f"docling失败 ({type(e).__name__})，降级到readability"
                    )
                    extracted_text = self._extract_with_readability(content)
                else:
                    if not extracted_text or not extracted_text.strip():
                        logger.warning(
                            "docling returned empty result, 降级到readability"
                        )
                        warnings.append(
                            "docling返回空结果，降级到readability"
                        )
                        extracted_text = self._extract_with_readability(content)
                    else:
                        warnings.append("使用docling(AI)提取HTML")
            else:
                logger.warning("docling不可用，降级到readability")
                warnings.append("docling不可用，降级到readability")
                extracted_text = self._extract_with_readability(content)
        else:
            extracted_text = self._extract_with_readability(content)
            quality_ok, quality_reason = self._check_quality(
                extracted_text, content
            )
            if not quality_ok and DOCLING_AVAILABLE:
                logger.info(
                    f"readability质量较低 ({quality_reason})，切换到docling"
                )
                warnings.append(
                    f"readability质量较低 ({quality_reason})，切换到docling"
                )
                # E2E-82: same fallback contract for the simple→docling path.
                try:
                    extracted_text = self._extract_with_docling(content)
                except Exception as e:
                    logger.warning(
                        f"docling failed ({type(e).__name__}: {e}), "
                        f"降级到readability"
                    )
                    warnings.append(
                        f"docling失败 ({type(e).__name__})，降级到readability"
                    )
                    # Keep the readability result we already have.
                else:
                    if not extracted_text or not extracted_text.strip():
                        logger.warning(
                            "docling returned empty result, using readability fallback"
                        )
                        warnings.append(
                            "docling返回空结果，使用readability结果"
                        )
                        # Keep the readability result.

        md_content = self._html_to_markdown(extracted_text, input_path.parent)
        paragraphs, table_row_indices = self._md_to_paragraphs_and_table_rows(
            md_content
        )

        images = self._extract_images(content, input_path.parent)

        table_cells = self._extract_table_cells(content)

        skeleton_html = self._generate_skeleton_html(content, paragraphs)

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=images,
            metadata=metadata,
            warnings=warnings,
            skeleton_html=skeleton_html,
            table_cells=table_cells,
            table_row_paragraph_indices=table_row_indices,
        )

    # ── Config / tool choice ─────────────────────────────────────

    def _get_tool_choice(self) -> str:
        """Determine which extraction engine to use (simple vs complex)."""
        try:
            from opp.config import get_config

            config = get_config()
            return config.get_extractor_mode("html")
        except Exception as e:
            logger.debug(f"Failed to get extractor mode config: {e}")
            return "simple"

    # ── Thin wrappers delegating to submodules ───────────────────

    def _detect_js_heavy(self, html_content: str) -> bool:
        return detect_js_heavy(html_content)

    def _extract_with_readability(self, html_content: str) -> str:
        return extract_with_readability(html_content)

    def _extract_with_docling(self, html_content: str) -> str:
        return extract_with_docling(html_content)

    def _extract_text_from_tree(self, tree: Any) -> str:
        return extract_text_from_tree(tree)

    def _strip_scripts_and_styles(self, html_content: str) -> str:
        return strip_scripts_and_styles(html_content)

    def _check_quality(
        self, extracted_text: str, original_html: str
    ) -> tuple[bool, str]:
        return check_quality(extracted_text, original_html)

    def _html_to_markdown(
        self,
        html_content: str,
        base_path: Path | None = None,
    ) -> str:
        return html_to_markdown(html_content, base_path)

    def _resolve_relative_paths(self, md_content: str, base_path: Path) -> str:
        return resolve_relative_paths(md_content, base_path)

    def _fix_tables(self, md_content: str) -> str:
        return fix_tables(md_content)

    def _check_table_broken(self, table_lines: list[str]) -> bool:
        return _check_table_broken(table_lines)

    # ── Paragraph / run parsing ──────────────────────────────────

    def _md_to_paragraphs(self, md_text: str) -> list[ParagraphData]:
        """Convert markdown text into a list of ``ParagraphData``.

        Parses heading levels, list styles, extract runs from inline
        HTML, and filters non-translatable content (base64 images).
        """
        return self._md_to_paragraphs_and_table_rows(md_text)[0]

    def _md_to_paragraphs_and_table_rows(
        self, md_text: str
    ) -> tuple[list[ParagraphData], frozenset[int]]:
        """Same as :meth:`_md_to_paragraphs`, plus the table-row paragraph indices.

        A markdown table is a contiguous run of ``|``-prefixed lines terminated by
        any other line — the same block definition :func:`fix_tables` uses. Those
        rows are the table's *rendering*, not DOM text, so ORF cannot write a
        translation back into them; the caller records their indices for the XLIFF
        generator to skip.
        """
        if not md_text:
            return [], frozenset()

        paragraphs = []
        table_row_indices: set[int] = set()
        lines = md_text.split("\n")
        in_table = False
        in_fence = False

        for line in lines:
            line = line.strip()
            if not line:
                if not in_fence:
                    in_table = False
                continue

            # A fenced block's content is verbatim: a ``|``-prefixed line inside
            # one is code/ASCII art, never a table row.
            if _RE_CODE_FENCE.match(line):
                in_fence = not in_fence
                in_table = False
            elif in_fence:
                in_table = False
            elif line.startswith("|"):
                in_table = True
            else:
                in_table = False

            level = None
            if line.startswith("#"):
                match = _RE_HEADING.match(line)
                if match:
                    level = len(match.group(1))
                    line = match.group(2)

            style = None
            if _RE_BULLET_LIST.match(line):
                style = "List"
            elif _RE_ORDERED_LIST.match(line):
                style = "Number"

            soup = BeautifulSoup(f"<div>{line}</div>", "html.parser")
            element = soup.find("div")
            runs = self.extract_runs(element)
            plain_text = "".join(r.text for r in runs) if runs else line

            # Filter out base64 markdown image references (non-translatable noise)
            if re.match(r"^\s*!\[.*?\]\(data:", plain_text):
                continue

            if in_table:
                table_row_indices.add(len(paragraphs))

            paragraphs.append(
                ParagraphData(
                    text=plain_text,
                    style=style,
                    level=level,
                    runs=runs,
                )
            )

        return paragraphs, frozenset(table_row_indices)

    # ── Table-cell extraction ───────────────────────────────────

    def _extract_table_cells(self, html_content: str) -> list[TableCellData]:
        """Return every non-empty ``<td>``/``<th>`` as a translatable cell.

        Tables are indexed in document order over the original HTML, nested
        tables included (``find_all("table")``). Rows/cells are the direct
        children only, matching ORF's ``table_{t}_r{r}_c{c}`` resolution.
        This is additive: the markdown output and skeleton are untouched.

        With ``OPP_TABLE_PARAGRAPH_UNITS`` OFF (the default) a non-empty cell is
        one bare unit whose text is space-joined -- unchanged. With it ON, a
        cell that has at least two direct block-level children and no stray
        (non-whitespace) inline content emits one ``_para{p}`` unit per
        non-empty block group instead; every other cell stays legacy.
        """
        # Cheap guard: most HTML inputs have no table, so avoid a second full
        # BeautifulSoup parse of a potentially huge document.
        if "<table" not in html_content.lower():
            return []

        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed for table cells: {e}")
            return []

        per_paragraph = is_table_paragraph_units_enabled()

        cells: list[TableCellData] = []
        for table_index, table in enumerate(soup.find_all("table")):
            for row, tr in enumerate(table.find_all("tr", recursive=False)):
                for col, cell in enumerate(
                    tr.find_all(["td", "th"], recursive=False)
                ):
                    if per_paragraph:
                        cells.extend(
                            _table_cell_units(cell, table_index, row, col)
                        )
                        continue
                    text = cell.get_text(" ", strip=True)
                    if text:
                        cells.append(TableCellData(
                            table_index=table_index,
                            row=row,
                            col=col,
                            text=text,
                        ))
        return cells

    # ── Skeleton HTML generation ─────────────────────────────────

    def _generate_skeleton_html(
        self,
        original_html: str,
        paragraphs: list[ParagraphData],
    ) -> str | None:
        """Inject ``data-trans-unit-id`` attributes on block elements matching paragraphs.

        Walks the original HTML DOM and annotates each block element
        whose text matches a paragraph with ``data-trans-unit-id="<id>"``.
        This allows ORF's primary DOM injection path to fire for HTML inputs.
        """
        if not paragraphs:
            return None

        soup = BeautifulSoup(original_html, "html.parser")

        block_tags = {
            "p",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "li",
            "td",
            "th",
            "article",
            "section",
            "header",
            "footer",
            "aside",
            "main",
            "nav",
        }

        # Index block elements by their text without calling ``get_text()`` per
        # element.  Per-element ``get_text`` is not viable: when a document
        # nests same-tag elements (malformed markup such as repeated unclosed
        # ``<p>``), element *k*'s subtree contains every later sibling, so each
        # call re-walks a growing subtree and the index build goes cubic.
        #
        # Two linear passes instead:
        #   1. every text node is attributed to its NEAREST block ancestor.  The
        #      walk up stops at the first block tag, so it costs inline-tag
        #      depth, not document depth.
        #   2. a block's full text is its own parts plus its nearest block
        #      children's full texts, folded deepest-first.  Parts are stripped
        #      and CONCATENATED with no separator (bs4 inserts nothing between
        #      them) and the result stripped again, which is exactly
        #      ``get_text(strip=True)``.  Joining with a space would turn
        #      "Hello <b>world</b>" into "Hello world" and stop matching the
        #      paragraph text.
        # ``block_tags`` is walked in its original order so the first matching
        # tag still wins and each text keeps its FIRST element, matching the
        # ``break``-on-first-hit behaviour of the original scan.
        block_names = _BLOCK_TEXT_TAGS
        blocks: dict[int, Any] = {}
        for tag in block_tags:
            for elem in soup.find_all(tag):
                blocks.setdefault(id(elem), elem)

        own_text: dict[int, list[str]] = {}
        for node in soup.descendants:
            parent = node.parent
            while parent is not None and getattr(parent, "name", None) not in block_names:
                parent = parent.parent
            if parent is None:
                continue
            if isinstance(node, NavigableString):
                text = str(node).strip()
                if text:
                    own_text.setdefault(id(parent), []).append(text)

        depth: dict[int, int] = {}
        for elem in blocks.values():
            base = 0
            cursor = elem.parent
            while cursor is not None:
                known = depth.get(id(cursor))
                if known is not None:
                    base = known
                    break
                cursor = cursor.parent
            depth[id(elem)] = base + 1

        full_text: dict[int, str] = {}
        for elem in sorted(blocks.values(), key=lambda e: depth[id(e)], reverse=True):
            parts = own_text.get(id(elem), [])
            cursor = elem.parent
            while cursor is not None and getattr(cursor, "name", None) not in block_names:
                cursor = cursor.parent
            if cursor is not None:
                child = full_text.get(id(cursor))
                if child:
                    full_text[id(cursor)] = child + "".join(parts)
                    continue
            full_text[id(elem)] = "".join(parts)

        elem_by_text: dict[str, Any] = {}
        for tag in block_tags:
            for elem in soup.find_all(tag):
                elem_text = full_text.get(id(elem), "").strip()
                if elem_text and elem_text not in elem_by_text:
                    elem_by_text[elem_text] = elem

        matched = 0
        for idx, para in enumerate(paragraphs):
            para_text = para.text.strip()
            if not para_text:
                continue

            elem = elem_by_text.get(para_text)
            if elem is not None:
                elem["data-trans-unit-id"] = f"para-{idx}"
                matched += 1

        if matched == 0:
            return None
        return str(soup)

    # ── Run / style extraction ───────────────────────────────────

    @staticmethod
    def _parse_style_attrs(element: Any) -> dict:
        """Parse ``font-family``, ``font-size``, ``color`` from an element's inline style."""
        style = element.get("style", "") if hasattr(element, "get") else ""
        if not style:
            return {}
        result: dict = {}
        m = re.search(r"font-family\s*:\s*([^;]+)", style, re.IGNORECASE)
        if m:
            family = m.group(1).strip().strip("'\"")
            family = family.split(",")[0].strip().strip("'\"")
            if family:
                result["font_name"] = family
        m = re.search(r"font-size\s*:\s*([^;]+)", style, re.IGNORECASE)
        if m:
            size_str = m.group(1).strip().lower()
            if size_str.endswith("pt"):
                try:
                    result["font_size"] = int(float(size_str[:-2].strip()) * 2)
                except ValueError:
                    pass
        m = re.search(r"color\s*:\s*([^;]+)", style, re.IGNORECASE)
        if m:
            color_str = m.group(1).strip()
            if color_str.startswith("#"):
                hex_color = color_str[1:].upper()
                if len(hex_color) == 3:
                    hex_color = "".join(c * 2 for c in hex_color)
                if len(hex_color) == 6:
                    result["color"] = hex_color
            elif color_str.startswith("rgb"):
                rgb_match = re.search(
                    r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str
                )
                if rgb_match:
                    r, g, b = rgb_match.groups()
                    result["color"] = f"{int(r):02X}{int(g):02X}{int(b):02X}"
        return result

    def extract_runs(self, element: Any) -> list[RunData]:
        """Extract inline formatting runs (bold, italic, etc.) from an HTML element."""
        from opp.utils.dataclasses import RunData

        runs = []
        tag_name = element.name if hasattr(element, "name") else None

        if tag_name in ("strong", "b", "em", "i", "u", "s", "del"):
            text = element.get_text()
            if text and text.strip():
                style_attrs = self._parse_style_attrs(element)
                runs.append(
                    RunData(
                        text=text,
                        bold=tag_name in ("strong", "b"),
                        italic=tag_name in ("em", "i"),
                        underline=tag_name == "u",
                        strike=tag_name in ("s", "del"),
                        font_size=style_attrs.get("font_size"),
                        font_name=style_attrs.get("font_name"),
                        color=style_attrs.get("color"),
                    )
                )
            return runs

        for child in element.children:
            if hasattr(child, "name") and child.name:
                bold = child.name in ("strong", "b")
                italic = child.name in ("em", "i")
                underline = child.name == "u"
                strike = child.name in ("s", "del")

                text = child.get_text()
                if text and text.strip():
                    style_attrs = self._parse_style_attrs(child)
                    runs.append(
                        RunData(
                            text=text,
                            bold=bold,
                            italic=italic,
                            underline=underline,
                            strike=strike,
                            font_size=style_attrs.get("font_size"),
                            font_name=style_attrs.get("font_name"),
                            color=style_attrs.get("color"),
                        )
                    )

                if child.name == "span":
                    child_runs = self.extract_runs(child)
                    runs.extend(child_runs)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    style_attrs = self._parse_style_attrs(element)
                    runs.append(
                        RunData(
                            text=text,
                            bold=False,
                            italic=False,
                            underline=False,
                            strike=False,
                            font_size=style_attrs.get("font_size"),
                            font_name=style_attrs.get("font_name"),
                            color=style_attrs.get("color"),
                        )
                    )

        return runs

    # ── Image extraction ─────────────────────────────────────────

    def _extract_images(
        self, html_content: str, base_dir: Path
    ) -> list[ImageData]:
        """Extract images from HTML content.

        Handles both data URI images (base64-embedded) and local file
        references relative to the HTML file.  Every extracted image
        is marked ``is_inline_in_md=True`` because markdownify already
        writes ``![alt](src)`` for every ``<img>`` (E2E-75).
        """
        result: list[ImageData] = []

        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}")
            return result

        page_by_div = {
            div: number
            for number, div in enumerate(soup.find_all("div", class_="page"), start=1)
        }

        for element_idx, img in enumerate(soup.find_all("img")):
            src = str(img.get("src", ""))
            if not src:
                continue

            if src.startswith(("http://", "https://", "//")):
                continue

            page_number = _page_number_for(img, page_by_div)

            if src.startswith("data:"):
                image_data = self._parse_data_uri(src)
                if image_data:
                    image_data.element_index = element_idx
                    image_data.page_number = page_number
                    # E2E-75: markdownify already writes ``![alt](src)``
                    # for every ``<img>``. The generator must NOT re-inject
                    # the ref nor append the image to the trailing block.
                    image_data.is_inline_in_md = True
                    result.append(image_data)
                continue

            try:
                img_path = (
                    base_dir / src
                    if not Path(src).is_absolute()
                    else Path(src)
                )
                if img_path.exists():
                    data = img_path.read_bytes()
                    mime_type = self._guess_mime_type(src)
                    result.append(
                        ImageData(
                            data=data,
                            mime_type=mime_type,
                            element_index=element_idx,
                            page_number=page_number,
                            is_inline_in_md=True,
                        )
                    )
            except Exception as e:
                logger.debug(f"Image extraction failed for {src}: {e}")
                continue

        return result

    def _parse_data_uri(self, src: str) -> ImageData | None:
        """Decode a base64 data URI into an ``ImageData``."""
        match = _RE_DATA_URI.match(src)
        if not match:
            return None

        mime_type = match.group(1)
        data_str = match.group(2)

        try:
            data = base64.b64decode(data_str)
            return ImageData(data=data, mime_type=mime_type)
        except Exception as e:
            logger.debug(
                f"_parse_data_uri: base64 decode failed "
                f"for data URI (mime={mime_type}): {e}"
            )
            return None

    @staticmethod
    def _guess_mime_type(src: str) -> str:
        """Guess MIME type from a file extension."""
        ext = Path(src).suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        return mime_map.get(ext, "application/octet-stream")
