import base64
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup
from lxml import html

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ImageData, ParagraphData
from opp.utils.exceptions import CorruptedFileError

try:
    from markdownify import MarkdownConverter, markdownify
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
        def __init__(self, **options):
            options.setdefault("heading_style", "atx")
            options.setdefault("bullets", "-")
            options.setdefault("strip", ["script", "style"])
            super().__init__(**options)

        def convert_img(self, el, text, convert_as_inline=False, **_kwargs):
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

    def supported_extensions(self) -> List[str]:
        return [".html", ".htm"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        file_metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            content = input_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = input_path.read_text(encoding="latin-1")
            except Exception as e:
                raise CorruptedFileError(f"无法读取HTML文件: {input_path}")

        metadata = DocumentMetadata(
            file_size=file_metadata.file_size,
            format_type="html",
        )

        if self._detect_js_heavy(content):
            warnings.append("JS-rendered page detected")

        extracted_text = self._extract_with_readability(content)
        quality_ok, quality_reason = self._check_quality(extracted_text, content)

        if not quality_ok:
            if DOCLING_AVAILABLE:
                warnings.append(f"Low quality from readability ({quality_reason}), switching to docling")
                extracted_text = self._extract_with_docling(content)
            else:
                warnings.append(f"Low quality detected ({quality_reason}), docling not available")

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

    def _extract_with_readability(self, html_content: str) -> str:
        if not READABILITY_AVAILABLE:
            return self._strip_scripts_and_styles(html_content)

        try:
            doc = readability.Document(html_content)
            summary = doc.summary()
            tree = html.fromstring(summary)
            return self._extract_text_from_tree(tree)
        except Exception:
            return self._strip_scripts_and_styles(html_content)

    def _extract_text_from_tree(self, tree) -> str:
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
        result = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        result = re.sub(r'<style[^>]*>.*?</style>', '', result, flags=re.DOTALL | re.IGNORECASE)
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
        except Exception:
            return ""

    def _md_to_paragraphs(self, md_text: str) -> List[ParagraphData]:
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
                match = re.match(r'^(#{1,6})\s+(.*)', line)
                if match:
                    level = len(match.group(1))
                    line = match.group(2)

            style = None
            if re.match(r'^[\-\*]\s+', line):
                style = "List"
            elif re.match(r'^\d+\.\s+', line):
                style = "Number"

            paragraphs.append(ParagraphData(
                text=line,
                style=style,
                level=level,
            ))

        return paragraphs

    def _extract_images(self, html_content: str, base_dir: Path) -> List[ImageData]:
        result: List[ImageData] = []

        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception:
            return result

        for img in soup.find_all("img"):
            src = str(img.get("src", ""))
            if not src:
                continue

            if src.startswith(("http://", "https://", "//")):
                continue

            if src.startswith("data:"):
                image_data = self._parse_data_uri(src)
                if image_data:
                    result.append(image_data)
                continue

            try:
                img_path = base_dir / src if not Path(src).is_absolute() else Path(src)
                if img_path.exists():
                    data = img_path.read_bytes()
                    mime_type = self._guess_mime_type(src)
                    result.append(ImageData(data=data, mime_type=mime_type))
            except Exception:
                continue

        return result

    def _parse_data_uri(self, src: str) -> Optional[ImageData]:
        match = re.match(r"data:([^;]+);base64,(.+)$", src)
        if not match:
            return None

        mime_type = match.group(1)
        data_str = match.group(2)

        try:
            data = base64.b64decode(data_str)
            return ImageData(data=data, mime_type=mime_type)
        except Exception:
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
        js_indicators = [
            r"react",
            r"vue",
            r"angular",
            r"ember\.js",
            r"mithril\.js",
            r"preact",
            r"solid\.js",
            r"svelte",
            r"jquery",
            r"prototype\.js",
            r"dojo",
            r"ext\.js",
            r" mootools",
            r"scriptaculous",
            r"node_modules",
            r"webpack",
            r"vite",
            r"next\.js",
            r"nuxt",
            r"gatsby",
            r"11ty",
            r"jekyll",
            r"hugo",
            r"angular\.js",
            r"underscore\.js",
            r"lazy\.js",
            r" lodash",
        ]

        content_lower = html_content.lower()
        for pattern in js_indicators:
            if re.search(pattern, content_lower):
                return True

        script_tags = re.findall(r"<script[^>]*>", html_content)
        for tag in script_tags:
            if "src=" in tag and len(tag) > 50:
                return True

        return False

    def _html_to_markdown(self, html_content: str, base_path: Optional[Path] = None) -> str:
        if not MARKDOWNIFY_AVAILABLE:
            return self._strip_scripts_and_styles(html_content)

        try:
            tree = html.fromstring(html_content)
            md_content = _HTMLMarkdownConverter().convert_soup(tree)

            if base_path:
                md_content = self._resolve_relative_paths(md_content, base_path)

            md_content = self._fix_tables(md_content)
            return md_content
        except Exception:
            return self._strip_scripts_and_styles(html_content)

    def _resolve_relative_paths(self, md_content: str, base_path: Path) -> str:
        def replace_src(match):
            alt = match.group(1)
            src = match.group(2)
            title = match.group(3) or ""

            if src.startswith(("http://", "https://", "//", "data:")):
                return match.group(0)

            try:
                img_path = base_path / src if not Path(src).is_absolute() else Path(src)
                resolved = img_path.resolve().as_posix()
                return f"![{alt}]({resolved}{title})"
            except Exception:
                return match.group(0)

        return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)({[^}]*})?", replace_src, md_content)

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

    def _check_table_broken(self, table_lines: List[str]) -> bool:
        if len(table_lines) < 2:
            return False

        pipe_counts = [line.count("|") for line in table_lines]
        if len(set(pipe_counts)) > 1:
            return True

        return False