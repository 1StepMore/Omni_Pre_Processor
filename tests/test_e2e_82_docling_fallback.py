"""E2E-82 regression tests.

The bug: ``HTMLExtractor.extract`` called docling via
``_extract_with_docling`` which returned ``""`` on any failure
(exception or empty result) AND silently swallowed the exception
(``logger.debug`` only). The two places that called docling had
asymmetric behavior:
  - ``complex`` mode + docling NOT installed → fall back to
    readability ✅
  - ``complex`` mode + docling installed but fails → silently use
    empty result ❌
  - ``simple`` mode → readability → if quality low, try docling →
    same silent-empty-failure ❌

The user-visible symptom: a 10MB HTML page with a docling timeout
or OOM produces a 0-character ``.md`` with only a misleading
"使用docling(AI)提取HTML" success warning. No fallback, no error.

The fix: every docling call site now wraps the call in try/except,
checks the returned text is non-empty, and falls back to readability
with a clear warning. Both the ``complex→docling`` and
``simple→readability→docling`` paths get the same contract.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from opp.extractors import html as html_mod
from opp.extractors.html import HTMLExtractor


SIMPLE_HTML = """<html>
<head><title>Test</title></head>
<body>
<h1>Hello World</h1>
<p>This is a test paragraph with enough text to be useful.</p>
<p>Another paragraph so readability produces non-empty output.</p>
</body>
</html>"""


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.html"
    p.write_text(SIMPLE_HTML, encoding="utf-8")
    return p


@pytest.fixture
def make_tool_choice():
    """Force ``tool_choice`` to a specific value without going through
    the config layer (which varies by env)."""
    def _set(value: str):
        from opp.extractors.html import HTMLExtractor
        return patch.object(HTMLExtractor, "_get_tool_choice", lambda self: value)
    return _set


class TestDoclingRaisesFallbackToReadability:
    """When docling raises (e.g. timeout, OOM), readability is used."""

    def test_complex_mode_docling_raises(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", True)
        # Force _extract_with_docling to raise.
        def boom(self, content):
            raise RuntimeError("simulated docling timeout")
        monkeypatch.setattr(
            HTMLExtractor, "_extract_with_docling", boom
        )
        with make_tool_choice("complex"):
            result = HTMLExtractor().extract(html_file)
        # Should not crash; should produce content from readability.
        assert result.paragraphs, (
            f"After docling failure, readability fallback should produce "
            f"paragraphs. Got: {result.paragraphs}"
        )
        # The warning must be present.
        assert any("docling" in w.lower() for w in result.warnings), (
            f"Must log that docling failed and fell back. "
            f"Warnings: {result.warnings}"
        )

    def test_simple_mode_docling_raises(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", True)
        def boom(self, content):
            raise RuntimeError("simulated docling OOM")
        monkeypatch.setattr(
            HTMLExtractor, "_extract_with_docling", boom
        )
        # Force readability quality check to fail so docling is tried.
        monkeypatch.setattr(
            HTMLExtractor, "_check_quality",
            lambda self, ext, orig: (False, "forced low quality"),
        )
        with make_tool_choice("simple"):
            result = HTMLExtractor().extract(html_file)
        # readability should be used (it always runs in simple mode)
        assert result.paragraphs
        # Warning should mention docling failure
        assert any("docling" in w.lower() for w in result.warnings), (
            f"Warnings: {result.warnings}"
        )


class TestDoclingEmptyResultFallback:
    """When docling returns empty/whitespace, readability is used."""

    def test_complex_mode_docling_returns_empty(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", True)
        monkeypatch.setattr(
            HTMLExtractor, "_extract_with_docling",
            lambda self, content: "",
        )
        with make_tool_choice("complex"):
            result = HTMLExtractor().extract(html_file)
        assert result.paragraphs, (
            f"After docling returns empty, readability must run. "
            f"Got: {result.paragraphs}"
        )
        assert any(
            "空结果" in w or "empty" in w.lower() for w in result.warnings
        ), f"Warnings: {result.warnings}"

    def test_complex_mode_docling_returns_whitespace_only(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", True)
        monkeypatch.setattr(
            HTMLExtractor, "_extract_with_docling",
            lambda self, content: "   \n  ",
        )
        with make_tool_choice("complex"):
            result = HTMLExtractor().extract(html_file)
        assert result.paragraphs, (
            f"Whitespace-only docling result must trigger fallback. "
            f"Got: {result.paragraphs}"
        )


class TestDoclingSuccessDoesNotFallback:
    """When docling returns a real result, no fallback warning."""

    def test_complex_mode_docling_succeeds(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", True)
        monkeypatch.setattr(
            HTMLExtractor, "_extract_with_docling",
            lambda self, content: "<p>docling succeeded</p>",
        )
        with make_tool_choice("complex"):
            result = HTMLExtractor().extract(html_file)
        # No fallback warning.
        assert not any(
            "降级" in w or "fallback" in w.lower() or "失败" in w
            for w in result.warnings
        ), f"Should not emit fallback warning on success. Got: {result.warnings}"


class TestDoclingNotInstalledFallbackStillWorks:
    """When docling is not installed, readability is used (regression)."""

    def test_complex_mode_no_docling_uses_readability(
        self, html_file: Path, make_tool_choice, monkeypatch
    ):
        monkeypatch.setattr(html_mod, "DOCLING_AVAILABLE", False)
        with make_tool_choice("complex"):
            result = HTMLExtractor().extract(html_file)
        assert result.paragraphs
        assert any("不可用" in w for w in result.warnings), (
            f"Warnings: {result.warnings}"
        )
