"""Regression tests for issue #145: HTML list markers emitted twice.

``markdownify`` already writes ``- A`` / ``1. One``.  The paragraph parser
kept that marker in ``ParagraphData.text`` and ``MarkdownGenerator`` then
prepended another one, producing ``- - A`` / ``1. 1. One`` (and ordered
items all numbered ``1.``).
"""

import re
from pathlib import Path

import pytest

from opp.extractors.html import HTMLExtractor
from opp.extractors.html.markdown_converter import MARKDOWNIFY_AVAILABLE
from opp.markdown.generator import MarkdownGenerator

pytestmark = pytest.mark.skipif(
    not MARKDOWNIFY_AVAILABLE, reason="markdownify not installed"
)


def _convert(tmp_path: Path, body: str) -> str:
    """Run the HTML extractor (no readability) + markdown generator."""
    path = tmp_path / "input.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    result = HTMLExtractor(use_readability=False).extract(path)
    return MarkdownGenerator().generate(result)


def test_flat_lists_have_one_marker_each(tmp_path: Path):
    md = _convert(
        tmp_path,
        "<h1>T</h1><ul><li>A</li><li>B</li></ul>"
        "<ol><li>One</li><li>Two</li></ol>",
    )

    assert "- - " not in md
    assert re.search(r"^\s*\d+\. \d+\. ", md, re.MULTILINE) is None

    assert "# T" in md
    assert "- A" in md
    assert "- B" in md
    assert "1. One" in md
    assert "2. Two" in md


def test_nested_list_indent_and_single_marker(tmp_path: Path):
    md = _convert(
        tmp_path,
        "<ul><li>A<ul><li>A1</li><li>A2<ul><li>A2a</li></ul></li></ul></li>"
        "<li>B</li></ul>",
    )

    assert "- - " not in md
    assert "\n- A\n  - A1\n  - A2\n    - A2a\n- B" in md
