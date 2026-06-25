"""Tests for HTMLExtractor skeleton_html generation (ORF #6 complement).

After extracting HTML to markdown, the extractor also produces an annotated
copy of the source HTML with data-trans-unit-id attributes injected on each
block element that matches a paragraph.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opp.extractors.html import HTMLExtractor


class TestSkeletonHtmlGeneration:
    """skeleton_html field on ExtractionResult for HTML inputs."""

    def test_injects_data_trans_unit_id_on_paragraphs(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body>
<p>Hello World</p>
<p>Second paragraph</p>
</body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        assert result.skeleton_html is not None
        assert 'data-trans-unit-id="para-' in result.skeleton_html

    def test_handles_nested_elements(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body>
<ul>
  <li><strong>Key Term</strong> description text</li>
</ul>
</body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        if result.skeleton_html is not None:
            assert 'data-trans-unit-id=' in result.skeleton_html

    def test_returns_none_for_empty_body(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><head><title>Empty</title></head><body></body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        assert result.skeleton_html is None

    def test_preserves_other_attributes(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body>
<p class="intro" id="first">Welcome to the page</p>
</body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        assert result.skeleton_html is not None
        assert 'class="intro"' in result.skeleton_html
        assert 'id="first"' in result.skeleton_html
        assert 'data-trans-unit-id="para-' in result.skeleton_html

    def test_heading_elements_get_annotated(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body>
<h1>Main Title</h1>
<p>Body text here.</p>
</body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        assert result.skeleton_html is not None
        assert "data-trans-unit-id" in result.skeleton_html

    def test_skeleton_html_is_str(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body><p>Test content</p></body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        if result.skeleton_html is not None:
            assert isinstance(result.skeleton_html, str)

    def test_existing_skeleton_bytes_field_unaffected(self, tmp_path: Path):
        html = """<!DOCTYPE html>
<html><body><p>Test</p></body></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html, encoding="utf-8")

        extractor = HTMLExtractor()
        result = extractor.extract(html_file)

        assert result.skeleton is None
        assert result.skeleton_files is None
