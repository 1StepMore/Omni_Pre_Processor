"""Tests for _strip_structural_html_tags — OPP#36 regression guard."""

import re
import pytest
from opp.extractors.html.markdown_converter import _STRUCTURE_HTML_TAGS, _strip_structural_html_tags


class TestStructureHtmlTags:
    """Verify _STRUCTURE_HTML_TAGS correctly identifies structural HTML tags."""

    # ── Should match (bare tags) ──
    @pytest.mark.parametrize("tag", [
        "<html>", "</html>",
        "<head>", "</head>",
        "<body>", "</body>",
        "<!doctype html>",
        "<!DOCTYPE HTML>",
        "<  html  >",            # whitespace before & after tag name
        "<  /body  >",
    ])
    def test_matches_bare_tags(self, tag: str):
        assert _STRUCTURE_HTML_TAGS.match(tag), f"Should match: {tag!r}"

    # ── Should match (with attributes) — OPP#36 regression guard ──
    @pytest.mark.parametrize("tag", [
        '<html lang="en">',
        "<html lang='en'>",
        '<html lang="en" dir="ltr">',
        '<head profile="http://www.w3.org/1999/xhtml/vocab/">',
        '<body class="content">',
        '<body class="page" id="main">',
        '<!doctype html public "-//W3C//DTD XHTML 1.0 Transitional//EN">',
    ])
    def test_matches_tags_with_attributes(self, tag: str):
        assert _STRUCTURE_HTML_TAGS.match(tag), f"Should match: {tag!r}"

    # ── Should NOT match (content tags) ──
    @pytest.mark.parametrize("tag", [
        "<div>", "</div>",
        "<p>", "</p>",
        "<section>",
        "<article>",
        "<script>", "</script>",
        "<html5>",               # not a standard structural tag
        "<bodytext>",
    ])
    def test_does_not_match_content_tags(self, tag: str):
        assert not _STRUCTURE_HTML_TAGS.match(tag), f"Should NOT match: {tag!r}"

    # ── Integration test: _strip_structural_html_tags ──
    def test_strips_tags_with_attributes(self):
        md_text = """<html lang="en">
<head><title>Test</title></head>
<body class="main">
<p>Hello</p>
</body>
</html>"""
        result = _strip_structural_html_tags(md_text)
        assert "<html" not in result, "Structural <html> tag should be stripped"
        assert "<body" not in result, "Structural <body> tag should be stripped"
        assert "Hello" in result, "Content text should be preserved"
        assert "<p>" in result, "Content <p> tag should be preserved"
