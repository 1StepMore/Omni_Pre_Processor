import base64
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ImageData, ParagraphData, RunData
from opp.utils.exceptions import CorruptedFileError
from opp.logger import logger

# Pre-compiled regex patterns for performance
_RE_SCRIPT_TAG = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
_RE_STYLE_TAG = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
_RE_HEADING = re.compile(r'^(#{1,6})\s+(.*)')
_RE_BULLET_LIST = re.compile(r'^[\-\*]\s+')
_RE_ORDERED_LIST = re.compile(r'^\d+\.\s+')
_RE_DATA_URI = re.compile(r"data:([^;]+);base64,(.+)$")
_RE_SCRIPT_TAG_SIMPLE = re.compile(r"<script[^>]*>")
_RE_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)({[^}]*})?")
_RE_JS_PATTERNS = [
    re.compile(r"react"),
    re.compile(r"vue"),
    re.compile(r"angular"),
    re.compile(r"ember\.js"),
    re.compile(r"mithril\.js"),
    re.compile(r"preact"),
    re.compile(r"solid\.js"),
    re.compile(r"svelte"),
    re.compile(r"jquery"),
    re.compile(r"prototype\.js"),
    re.compile(r"dojo"),
    re.compile(r"ext\.js"),
    re.compile(r" mootools"),
    re.compile(r"scriptaculous"),
    re.compile(r"node_modules"),
    re.compile(r"webpack"),
    re.compile(r"vite"),
    re.compile(r"next\.js"),
    re.compile(r"nuxt"),
    re.compile(r"gatsby"),
    re.compile(r"11ty"),
    re.compile(r"jekyll"),
    re.compile(r"hugo"),
    re.compile(r"angular\.js"),
    re.compile(r"underscore\.js"),
    re.compile(r"lazy\.js"),
    re.compile(r" lodash"),
]

try:
    from markdownify import MarkdownConverter
    MARKDOWNIFY_AVAILABLE = True
except ImportError:
    MARKDOWNIFY_AVAILABLE = False

try:
    from readability import readability
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False

try:
    from docling.core.processor.html_processor import HtmlPageProcessor
    from docling.datamodel.document import DoclingDocument
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


if MARKDOWNIFY_AVAILABLE:
    class _HTMLMarkdownConverter(MarkdownConverter):
        def __init__(self, **options: Any) -> None:
            options.setdefault("heading_style", "atx")
            options.setdefault("bullets", "-")
            options.setdefault("strip", ["script", "style"])
            super().__init__(**options)

        def convert_img(self, el: Any, _text: Any, _convert_as_inline: bool = False, **_kwargs: Any) -> str:
            alt = el.get("alt", "") or ""
            src = el.get("src", "") or el.get("data-src", "") or ""
            title = el.get("title", "") or ""
            title_part = f' "{title}"' if title else ""
            alt_clean = alt.replace("\n", " ")
            if src.startswith("data:") and not self.options.get("keep_data_uris", False):
                src = src.split(",")[0] + "..."
            return f"![{alt_clean}]({src}{title_part})"
else:
    _HTMLMarkdownConverter = None


class HTMLExtractor(ExtractorBase):

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
                extracted_text = self._extract_with_docling(content)
                warnings.append("使用docling(AI)提取HTML")
            else:
                logger.warning("docling不可用，降级到readability")
                warnings.append("docling不可用，降级到readability")
                extracted_text = self._extract_with_readability(content)
        else:
            extracted_text = self._extract_with_readability(content)
            quality_ok, quality_reason = self._check_quality(extracted_text, content)
            if not quality_ok and DOCLING_AVAILABLE:
                logger.info(f"readability质量较低 ({quality_reason})，切换到docling")
                warnings.append(f"readability质量较低 ({quality_reason})，切换到docling")
                extracted_text = self._extract_with_docling(content)

        md_content = self._html_to_markdown(extracted_text, input_path.parent)
        paragraphs = self._md_to_paragraphs(md_content)

        images = self._extract_images(content, input_path.parent)

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def _get_tool_choice(self) -> str:
        try:
            from opp.config import get_config
            config = get_config()
            return config.get_extractor_mode("html")
        except Exception as e:
            logger.debug(f"Failed to get extractor mode config: {e}")
            return "simple"

    def _extract_with_readability(self, html_content: str) -> str:
        if not READABILITY_AVAILABLE:
            stripped = self._strip_scripts_and_styles(html_content)
            return stripped

        try:
            doc = readability.Document(html_content)
            return doc.summary()  # Return raw HTML for markdownify conversion
        except Exception as e:
            logger.debug(f"Readability extraction failed: {e}")
            return self._strip_scripts_and_styles(html_content)

    def _extract_text_from_tree(self, tree: Any) -> str:
        for elem in tree.findall(".//script"):
            elem.getparent().remove(elem)
        for elem in tree.findall(".//style"):
            elem.getparent().remove(elem)

        text_parts = []
        for elem in tree.iter():
            if elem.tag in ("p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6",
                           "article", "section", "br"):
                if elem.text:
                    text_parts.append(elem.text)
                if elem.tail:
                    text_parts.append(elem.tail)
        return "\n".join(text_parts)

    def _strip_scripts_and_styles(self, html_content: str) -> str:
        result = _RE_SCRIPT_TAG.sub('', html_content)
        result = _RE_STYLE_TAG.sub('', result)
        return result

    def _check_quality(self, extracted_text: str, original_html: str) -> tuple[bool, str]:
        if not extracted_text or len(extracted_text.strip()) == 0:
            return False, "empty output"

        text_lower = extracted_text.lower()
        noise_markers = ["sidebar", "navigation", "nav-", "footer", "menu", "header"]
        noise_count = sum(1 for m in noise_markers if m in text_lower)
        if noise_count >= 3:
            return False, "nav/sidebar/footer detected"

        original_text_length = len(self._strip_scripts_and_styles(original_html))
        if original_text_length > 0:
            text_ratio = len(extracted_text) / original_text_length
            if text_ratio < 0.5:
                return False, f"low text ratio ({text_ratio:.2f})"

        if len(extracted_text) < 100 and original_text_length > 500:
            return False, "output too short relative to input"

        return True, "ok"

    def _extract_with_docling(self, html_content: str) -> str:
        if not DOCLING_AVAILABLE:
            return ""

        try:
            processor = HtmlPageProcessor()
            result = processor.process(html_content)
            if isinstance(result, DoclingDocument):
                return result.export_to_markdown()
            return str(result)
        except Exception as e:
            logger.debug(f"Docling extraction failed: {e}")
            return ""

    def _md_to_paragraphs(self, md_text: str) -> list[ParagraphData]:
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
            element = soup.find('div')
            runs = self.extract_runs(element)
            plain_text = ''.join(r.text for r in runs) if runs else line

            paragraphs.append(ParagraphData(
                text=plain_text,
                style=style,
                level=level,
                runs=runs,
            ))

        return paragraphs

    @staticmethod
    def _parse_style_attrs(element: Any) -> dict:
        """Parse font-family, font-size, color from an element's inline style."""
        style = element.get('style', '') if hasattr(element, 'get') else ''
        if not style:
            return {}
        result: dict = {}
        m = re.search(r'font-family\s*:\s*([^;]+)', style, re.IGNORECASE)
        if m:
            family = m.group(1).strip().strip('"\'')
            family = family.split(',')[0].strip().strip('"\'')
            if family:
                result['font_name'] = family
        m = re.search(r'font-size\s*:\s*([^;]+)', style, re.IGNORECASE)
        if m:
            size_str = m.group(1).strip().lower()
            if size_str.endswith('pt'):
                try:
                    result['font_size'] = int(float(size_str[:-2].strip()) * 2)
                except ValueError:
                    pass
        m = re.search(r'color\s*:\s*([^;]+)', style, re.IGNORECASE)
        if m:
            color_str = m.group(1).strip()
            if color_str.startswith('#'):
                hex_color = color_str[1:].upper()
                if len(hex_color) == 3:
                    hex_color = ''.join(c * 2 for c in hex_color)
                if len(hex_color) == 6:
                    result['color'] = hex_color
            elif color_str.startswith('rgb'):
                rgb_match = re.search(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
                if rgb_match:
                    r, g, b = rgb_match.groups()
                    result['color'] = f'{int(r):02X}{int(g):02X}{int(b):02X}'
        return result

    def extract_runs(self, element: Any) -> list[RunData]:
        from opp.utils.dataclasses import RunData

        runs = []
        tag_name = element.name if hasattr(element, 'name') else None

        if tag_name in ('strong', 'b', 'em', 'i', 'u', 's', 'del'):
            text = element.get_text()
            if text and text.strip():
                style_attrs = self._parse_style_attrs(element)
                runs.append(RunData(
                    text=text,
                    bold=tag_name in ('strong', 'b'),
                    italic=tag_name in ('em', 'i'),
                    underline=tag_name == 'u',
                    strike=tag_name in ('s', 'del'),
                    font_size=style_attrs.get('font_size'),
                    font_name=style_attrs.get('font_name'),
                    color=style_attrs.get('color'),
                ))
            return runs

        for child in element.children:
            if hasattr(child, 'name') and child.name:
                bold = child.name in ('strong', 'b')
                italic = child.name in ('em', 'i')
                underline = child.name == 'u'
                strike = child.name in ('s', 'del')

                text = child.get_text()
                if text and text.strip():
                    style_attrs = self._parse_style_attrs(child)
                    runs.append(RunData(
                        text=text,
                        bold=bold,
                        italic=italic,
                        underline=underline,
                        strike=strike,
                        font_size=style_attrs.get('font_size'),
                        font_name=style_attrs.get('font_name'),
                        color=style_attrs.get('color'),
                    ))

                if child.name == 'span':
                    child_runs = self.extract_runs(child)
                    runs.extend(child_runs)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    style_attrs = self._parse_style_attrs(element)
                    runs.append(RunData(
                        text=text,
                        bold=False,
                        italic=False,
                        underline=False,
                        strike=False,
                        font_size=style_attrs.get('font_size'),
                        font_name=style_attrs.get('font_name'),
                        color=style_attrs.get('color'),
                    ))

        return runs

    def _extract_images(self, html_content: str, base_dir: Path) -> list[ImageData]:
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
                    # E2E-75: ``_html_to_markdown`` (markdownify) already
                    # writes ``![alt](src)`` for every ``<img>``. The
                    # generator must NOT re-inject the ref nor append the
                    # image to the ``## Images`` trailing block.
                    image_data.is_inline_in_md = True
                    result.append(image_data)
                continue

            try:
                img_path = base_dir / src if not Path(src).is_absolute() else Path(src)
                if img_path.exists():
                    data = img_path.read_bytes()
                    mime_type = self._guess_mime_type(src)
                    result.append(ImageData(
                        data=data,
                        mime_type=mime_type,
                        element_index=element_idx,
                        is_inline_in_md=True,
                    ))
            except Exception as e:
                logger.debug(f"Image extraction failed for {src}: {e}")
                continue

        return result

    def _parse_data_uri(self, src: str) -> ImageData | None:
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
                f"_parse_data_uri: base64 decode failed for data URI (mime={mime_type}): {e}"
            )
            return None

    def _guess_mime_type(self, src: str) -> str:
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

    def _detect_js_heavy(self, html_content: str) -> bool:
        content_lower = html_content.lower()
        for pattern in _RE_JS_PATTERNS:
            if pattern.search(content_lower):
                return True

            script_tags = _RE_SCRIPT_TAG_SIMPLE.findall(html_content)
        for tag in script_tags:
            if "src=" in tag and len(tag) > 50:
                return True

        return False

    def _html_to_markdown(self, html_content: str, base_path: Path | None = None) -> str:
        if not MARKDOWNIFY_AVAILABLE:
            return self._strip_scripts_and_styles(html_content)

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            md_content = _HTMLMarkdownConverter().convert_soup(soup)

            if base_path:
                md_content = self._resolve_relative_paths(md_content, base_path)

            md_content = self._fix_tables(md_content)
            return md_content
        except Exception as e:
            logger.debug(f"Markdown conversion failed: {e}")
            return self._strip_scripts_and_styles(html_content)

    def _resolve_relative_paths(self, md_content: str, base_path: Path) -> str:
        def replace_src(match: Any) -> str:
            alt = match.group(1)
            src = match.group(2)
            title = match.group(3) or ""

            if src.startswith(("http://", "https://", "//", "data:")):
                return match.group(0)

            try:
                img_path = base_path / src if not Path(src).is_absolute() else Path(src)
                resolved = img_path.resolve().as_posix()
                return f"![{alt}]({resolved}{title})"
            except Exception as e:
                logger.debug(f"Path resolution failed for {src}: {e}")
                return match.group(0)

        return _RE_MARKDOWN_IMAGE.sub(replace_src, md_content)

    def _fix_tables(self, md_content: str) -> str:
        lines = md_content.split("\n")
        result = []
        in_table = False
        table_lines = []

        for line in lines:
            if line.startswith("|"):
                table_lines.append(line)
                in_table = True
            else:
                if in_table:
                    if self._check_table_broken(table_lines):
                        result.append("<!-- complex table: HTML fallback -->")
                        for tl in table_lines:
                            result.append(tl)
                    else:
                        result.extend(table_lines)
                    table_lines = []
                    in_table = False
                result.append(line)

        if in_table:
            if self._check_table_broken(table_lines):
                result.append("<!-- complex table: HTML fallback -->")
                result.extend(table_lines)
            else:
                result.extend(table_lines)

        return "\n".join(result)

    def _check_table_broken(self, table_lines: list[str]) -> bool:
        if len(table_lines) < 2:
            return False

        pipe_counts = [line.count("|") for line in table_lines]
        if len(set(pipe_counts)) > 1:
            return True

        return False