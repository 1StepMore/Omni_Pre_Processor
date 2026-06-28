"""HTML-to-Markdown conversion and content extraction utilities.

Handles the conversion pipeline: readability/docling extraction →
markdownify conversion → table fixup → structural cleanup.
Used by HTMLExtractor for the ``extract()`` text processing steps.
"""

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from opp.logger import logger

# ── Optional dependencies ──────────────────────────────────────────

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

# ── Module-level regex patterns ────────────────────────────────────

_RE_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)({[^}]*})?")
_RE_SCRIPT_TAG = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_RE_STYLE_TAG = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_STRUCTURE_HTML_TAGS = re.compile(
    r"^<\s*(?:/?html|/?head|/?body|!doctype\s+html)\s*>$",
    re.IGNORECASE,
)


def _strip_structural_html_tags(md_text: str) -> str:
    """Remove lines that are bare structural HTML tags like ``<html>``, ``</body>``, etc."""
    return "\n".join(
        line
        for line in md_text.splitlines()
        if not _STRUCTURE_HTML_TAGS.match(line.strip())
    )


# ── Markdownify converter subclass ─────────────────────────────────

if MARKDOWNIFY_AVAILABLE:

    class _HTMLMarkdownConverter(MarkdownConverter):
        """Custom markdownify converter tailored for OPP extraction."""

        def __init__(self, **options: Any) -> None:
            options.setdefault("heading_style", "atx")
            options.setdefault("bullets", "-")
            options.setdefault("strip", ["script", "style"])
            super().__init__(**options)

        def convert_img(
            self,
            el: Any,
            _text: Any,
            _convert_as_inline: bool = False,
            **_kwargs: Any,
        ) -> str:
            alt = el.get("alt", "") or ""
            src = el.get("src", "") or el.get("data-src", "") or ""
            title = el.get("title", "") or ""
            title_part = f' "{title}"' if title else ""
            alt_clean = alt.replace("\n", " ")
            if src.startswith("data:") and not self.options.get(
                "keep_data_uris", False
            ):
                src = src.split(",")[0] + "..."
            return f"![{alt_clean}]({src}{title_part})"

else:
    _HTMLMarkdownConverter = None


# ── Content extraction functions ───────────────────────────────────

def extract_with_readability(html_content: str) -> str:
    """Extract readable content using the readability library.

    Falls back to ``strip_scripts_and_styles()`` if readability is
    not installed or raises.
    """
    if not READABILITY_AVAILABLE:
        return strip_scripts_and_styles(html_content)

    try:
        doc = readability.Document(html_content)
        return doc.summary()  # Return raw HTML for markdownify conversion
    except Exception as e:
        logger.debug(f"Readability extraction failed: {e}")
        return strip_scripts_and_styles(html_content)


def extract_with_docling(html_content: str) -> str:
    """Extract content using the docling (AI) HTML processor.

    Returns an empty string if docling is unavailable or fails.
    """
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


def extract_text_from_tree(tree: Any) -> str:
    """Extract plain text from an lxml/BeautifulSoup tree, removing scripts and styles."""
    for elem in tree.findall(".//script"):
        elem.getparent().remove(elem)
    for elem in tree.findall(".//style"):
        elem.getparent().remove(elem)

    text_parts = []
    for elem in tree.iter():
        if elem.tag in (
            "p",
            "div",
            "span",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "article",
            "section",
            "br",
        ):
            if elem.text:
                text_parts.append(elem.text)
            if elem.tail:
                text_parts.append(elem.tail)
    return "\n".join(text_parts)


def strip_scripts_and_styles(html_content: str) -> str:
    """Remove ``<script>`` and ``<style>`` tags and their content."""
    result = _RE_SCRIPT_TAG.sub("", html_content)
    result = _RE_STYLE_TAG.sub("", result)
    return result


def check_quality(extracted_text: str, original_html: str) -> tuple[bool, str]:
    """Evaluate extraction quality heuristically.

    Returns ``(ok: bool, reason: str)`` where ``reason`` explains
    why quality was deemed insufficient.
    """
    if not extracted_text or len(extracted_text.strip()) == 0:
        return False, "empty output"

    text_lower = extracted_text.lower()
    noise_markers = [
        "sidebar",
        "navigation",
        "nav-",
        "footer",
        "menu",
        "header",
    ]
    noise_count = sum(1 for m in noise_markers if m in text_lower)
    if noise_count >= 3:
        return False, "nav/sidebar/footer detected"

    original_text_length = len(strip_scripts_and_styles(original_html))
    if original_text_length > 0:
        text_ratio = len(extracted_text) / original_text_length
        if text_ratio < 0.5:
            return False, f"low text ratio ({text_ratio:.2f})"

    if len(extracted_text) < 100 and original_text_length > 500:
        return False, "output too short relative to input"

    return True, "ok"


# ── Markdown conversion pipeline ───────────────────────────────────

def html_to_markdown(
    html_content: str,
    base_path: Path | None = None,
) -> str:
    """Convert HTML content to Markdown.

    Uses markdownify (if available) then applies table fixup,
    path resolution, and structural tag removal.
    """
    if not MARKDOWNIFY_AVAILABLE:
        return strip_scripts_and_styles(html_content)

    try:
        from .table_extractor import fix_tables

        soup = BeautifulSoup(html_content, "html.parser")
        md_content = _HTMLMarkdownConverter().convert_soup(soup)

        if base_path:
            md_content = resolve_relative_paths(md_content, base_path)

        md_content = fix_tables(md_content)
        md_content = _strip_structural_html_tags(md_content)
        return md_content
    except Exception as e:
        logger.debug(f"Markdown conversion failed: {e}")
        return strip_scripts_and_styles(html_content)


def resolve_relative_paths(md_content: str, base_path: Path) -> str:
    """Resolve relative image paths in markdown to absolute paths."""

    def replace_src(match: Any) -> str:
        alt = match.group(1)
        src = match.group(2)
        title = match.group(3) or ""

        if src.startswith(("http://", "https://", "//", "data:")):
            return match.group(0)

        try:
            img_path = (
                base_path / src if not Path(src).is_absolute() else Path(src)
            )
            resolved = img_path.resolve().as_posix()
            return f"![{alt}]({resolved}{title})"
        except Exception as e:
            logger.debug(f"Path resolution failed for {src}: {e}")
            return match.group(0)

    return _RE_MARKDOWN_IMAGE.sub(replace_src, md_content)
