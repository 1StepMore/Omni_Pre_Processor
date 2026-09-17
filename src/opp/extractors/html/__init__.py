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

from bs4 import BeautifulSoup, NavigableString

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
)
from opp.utils.exceptions import CorruptedFileError

# ── Module-level regex patterns (used by methods in this module) ───

_RE_DATA_URI = re.compile(r"data:([^;]+);base64,(.+)$")
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.*)")
_RE_BULLET_LIST = re.compile(r"^[\-\*]\s+")
_RE_ORDERED_LIST = re.compile(r"^\d+\.\s+")


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
        paragraphs = self._md_to_paragraphs(md_content)

        images = self._extract_images(content, input_path.parent)

        skeleton_html = self._generate_skeleton_html(content, paragraphs)

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=images,
            metadata=metadata,
            warnings=warnings,
            skeleton_html=skeleton_html,
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
        if not md_text:
            return []

        paragraphs = []
        lines = md_text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

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

            paragraphs.append(
                ParagraphData(
                    text=plain_text,
                    style=style,
                    level=level,
                    runs=runs,
                )
            )

        return paragraphs

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

        matched = 0
        for idx, para in enumerate(paragraphs):
            para_text = para.text.strip()
            if not para_text:
                continue

            unit_id = f"para-{idx}"
            for tag in block_tags:
                for elem in soup.find_all(tag):
                    elem_text = elem.get_text(strip=True)
                    if elem_text == para_text:
                        elem["data-trans-unit-id"] = unit_id
                        matched += 1
                        break
                else:
                    continue
                break

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

        for element_idx, img in enumerate(soup.find_all("img")):
            src = str(img.get("src", ""))
            if not src:
                continue

            if src.startswith(("http://", "https://", "//")):
                continue

            if src.startswith("data:"):
                image_data = self._parse_data_uri(src)
                if image_data:
                    image_data.element_index = element_idx
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
