"""Regression tests for HTMLExtractor split (Task 3.8).

Verifies that after splitting ``html.py`` into separate sub-modules,
all imports, symbols, and extraction behavior remain unchanged.
"""

from pathlib import Path

import pytest

# ── 1. Backward-compatible imports ────────────────────────────────


def test_import_htmlextractor():
    """The primary public import path must still work."""
    from opp.extractors.html import HTMLExtractor

    assert HTMLExtractor is not None


def test_import_html_module():
    """``from opp.extractors import html as html_mod`` must still work
    (used by tests that patch ``DOCLING_AVAILABLE`` et al.)."""
    from opp.extractors import html as html_mod

    assert hasattr(html_mod, "HTMLExtractor")
    assert hasattr(html_mod, "DOCLING_AVAILABLE")
    assert hasattr(html_mod, "MARKDOWNIFY_AVAILABLE")
    assert hasattr(html_mod, "READABILITY_AVAILABLE")


# ── 2. Sub-module imports ─────────────────────────────────────────


def test_spa_detector_import():
    """The spa_detector sub-module is importable."""
    from opp.extractors.html.spa_detector import detect_js_heavy

    assert callable(detect_js_heavy)


def test_spa_detector_patterns_exists():
    """The 30 JS regex patterns are accessible."""
    from opp.extractors.html.spa_detector import _RE_JS_PATTERNS

    assert len(_RE_JS_PATTERNS) == 27  # 27 entries in the list (some have 2 patterns each)


def test_markdown_converter_import():
    """The markdown_converter sub-module is importable."""
    from opp.extractors.html.markdown_converter import (
        MARKDOWNIFY_AVAILABLE,
        html_to_markdown,
        strip_scripts_and_styles,
        extract_with_readability,
    )

    assert callable(html_to_markdown)
    assert callable(strip_scripts_and_styles)
    assert callable(extract_with_readability)


def test_table_extractor_import():
    """The table_extractor sub-module is importable."""
    from opp.extractors.html.table_extractor import fix_tables, _check_table_broken

    assert callable(fix_tables)
    assert callable(_check_table_broken)


# ── 3. SPA detector functionality ─────────────────────────────────


def test_spa_detector_detects_react():
    """SPA detector should flag React-based HTML."""
    from opp.extractors.html.spa_detector import detect_js_heavy

    html = '<html><head><script src="react.js"></script></head><body><div id="root"></div></body></html>'
    assert detect_js_heavy(html) is True


def test_spa_detector_plain_html():
    """SPA detector should NOT flag static HTML."""
    from opp.extractors.html.spa_detector import detect_js_heavy

    html = "<html><body><p>Hello world</p></body></html>"
    assert detect_js_heavy(html) is False


# ── 4. Markdown converter functionality ───────────────────────────


def test_strip_scripts_and_styles():
    """Stripping <script> and <style> tags works."""
    from opp.extractors.html.markdown_converter import strip_scripts_and_styles

    html = "<html><head><style>body{color:red}</style></head><body><p>Hello</p><script>alert('x')</script></body></html>"
    result = strip_scripts_and_styles(html)
    assert "alert" not in result
    assert "color:red" not in result
    assert "Hello" in result


def test_strip_structural_html_tags():
    """Structural HTML tags are removed from markdown output."""
    from opp.extractors.html.markdown_converter import _strip_structural_html_tags

    md = "<html>\n<head>\n</head>\n<body>\n<p>Hello</p>\n</body>\n</html>"
    result = _strip_structural_html_tags(md)
    assert "<html>" not in result
    assert "<body>" not in result
    assert "<p>Hello</p>" in result


def test_html_to_markdown_fallback():
    """When markdownify is unavailable, ``html_to_markdown`` falls back to stripping."""
    from opp.extractors.html.markdown_converter import html_to_markdown

    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    result = html_to_markdown(html)
    # Without markdownify, result is just stripped of script/style tags
    assert "Hello" in result


# ── 5. Table extractor functionality ──────────────────────────────


def test_fix_tables_passthrough():
    """``fix_tables`` passes through non-table lines unchanged."""
    from opp.extractors.html.table_extractor import fix_tables

    md = "Some text\n\nMore text"
    assert fix_tables(md) == md


def test_fix_tables_consistent():
    """``fix_tables`` leaves consistent tables alone."""
    from opp.extractors.html.table_extractor import fix_tables

    md = "| H1 | H2 |\n|---|---|\n| A | B |"
    assert fix_tables(md) == md


def test_fix_tables_broken():
    """``fix_tables`` marks inconsistent tables with a comment."""
    from opp.extractors.html.table_extractor import fix_tables

    md = "| H1 | H2 |\n| A | B | C |"
    result = fix_tables(md)
    assert "<!-- complex table" in result


# ── 6. HTMLExtractor integration ──────────────────────────────────


def test_htmlextractor_supported_extensions():
    """``supported_extensions`` returns expected formats."""
    from opp.extractors.html import HTMLExtractor

    ext = HTMLExtractor()
    assert ext.supported_extensions() == [".html", ".htm"]


def test_htmlextractor_extract_basic(tmp_path: Path):
    """Basic HTML extraction produces paragraphs."""
    from opp.extractors.html import HTMLExtractor

    html_file = tmp_path / "test.html"
    html_file.write_text(
        "<html><body><h1>Title</h1><p>Hello world</p></body></html>",
        encoding="utf-8",
    )

    ext = HTMLExtractor()
    result = ext.extract(html_file)
    assert len(result.paragraphs) > 0
    assert any("Hello" in p.text for p in result.paragraphs)


def test_htmlextractor_detects_spa(tmp_path: Path):
    """SPA detection warns on React-based pages."""
    from opp.extractors.html import HTMLExtractor

    html_file = tmp_path / "spa.html"
    html_file.write_text(
        '<html><head><script src="https://unpkg.com/react@18/umd/react.development.js"></script></head>'
        "<body><div id=\"root\"></div></body></html>",
        encoding="utf-8",
    )

    ext = HTMLExtractor()
    result = ext.extract(html_file)
    assert any("JS-rendered" in w for w in result.warnings)


def test_htmlextractor_parse_style_attrs():
    """Inline style parsing works."""
    from opp.extractors.html import HTMLExtractor

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        '<span style="font-family:Arial;font-size:12pt;color:#FF0000">text</span>',
        "html.parser",
    )
    attrs = HTMLExtractor._parse_style_attrs(soup.find("span"))
    assert attrs.get("font_name") == "Arial"
    assert attrs.get("font_size") == 24
    assert attrs.get("color") == "FF0000"


def test_htmlextractor_guess_mime_type():
    """MIME type guessing works for common extensions."""
    from opp.extractors.html import HTMLExtractor

    assert HTMLExtractor._guess_mime_type("image.png") == "image/png"
    assert HTMLExtractor._guess_mime_type("photo.jpg") == "image/jpeg"
    assert HTMLExtractor._guess_mime_type("icon.svg") == "image/svg+xml"
    assert HTMLExtractor._guess_mime_type("unknown.bin") == "application/octet-stream"
