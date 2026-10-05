"""OPP#97 — HTML extraction degraded silently instead of reporting it.

Two independent silent-wrong-output paths, both of which returned
``success`` with the text simply gone:

**(a) readability's "not enough content" verdict was accepted.**
``extract_with_readability`` returned ``doc.summary()`` unconditionally. That
call does not signal failure by returning ``""`` — it returns
``<body id="readabilityBody"></body>``, an empty body wrapped in markup. OPP
then handed that to markdownify, got ``""``, produced ``paragraphs=[]`` and
``content=''``, and reported success.

The condition that triggers it is *being small*, not *being broken*: every
page of a PDF goes through here via ``PDF2HTMLExtractor``, so a one-page PDF
lost its entire body. Measured on the matrix's minimal PDF fixture, whose only
text is ``Hello, world.``:

    before: PDF2HTMLExtractor -> 0 paragraphs, content=''
    after:  PDF2HTMLExtractor -> 1 paragraph,  content='Hello, world.'

Note the existing fixtures in ``test_pdf2html_extractor.py`` carry two
paragraphs and were never affected — which is why this survived: the failure
needs content thin enough for readability to reject, and nothing tested that.

**(b) A missing ``markdownify`` degraded HTML→Markdown with no warning.**
It lives in OPP's *optional* ``web`` extra, so a bare
``pip install -e Omni_Pre_Processor`` has none. ``html_to_markdown()`` then
returns the raw HTML, which gets parsed as if it were Markdown, so paragraph
text keeps its tags. Every block then collapses together, and because the
skeleton builder matches paragraph text against the document DOM, nothing
matches and no skeleton is produced. The observable effect — an HTML input
that yields XLIFF but no ``skeleton_path`` — points nowhere near an absent
package, so this now warns, and ``get_capabilities`` reports it up front.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from unittest.mock import patch

import pytest
from opp.extractors.html import HTMLExtractor
from opp.extractors.html.markdown_converter import (
    READABILITY_AVAILABLE,
    extract_with_readability,
    strip_scripts_and_styles,
)

# ── has_extractable_text ────────────────────────────────────────────


class TestHasExtractableText:
    # Imported lazily so that running this file against the *unfixed* source
    # collects and each behavioural test below fails on its own assertion,
    # rather than the whole file dying on a missing symbol.
    @staticmethod
    def _has_text(fragment: str) -> bool:
        from opp.extractors.html.markdown_converter import has_extractable_text

        return has_extractable_text(fragment)

    @pytest.mark.parametrize(
        ("fragment", "expected"),
        [
            # readability's verdict for content too thin to be "readable".
            ('<body id="readabilityBody">\n\n</body>', False),
            ("", False),
            ("   \n\t ", False),
            # Entities unescape to whitespace, which must not count as text.
            ("<body>&nbsp;</body>", False),
            # Markup with no text is not text.
            ('<body><img src="a.png"></body>', False),
            ("<body id=\"readabilityBody\"><p>Hello</p></body>", True),
            ("<body>plain text</body>", True),
        ],
    )
    def test_detects_text_presence(self, fragment: str, expected: bool):
        assert self._has_text(fragment) is expected


# ── (a) readability's empty verdict must not be accepted ────────────


class TestReadabilityEmptyVerdict:
    # These two assert how OPP interacts with readability itself, so they need
    # readability present — `markdown_converter` imports it at module scope and
    # the name does not exist when the optional dep is absent. OPP's own CI
    # installs it; the suite's CI installs OPP bare and does not, which is why
    # this is a skip on the library's own availability flag rather than an
    # assumption. The dep-free half of this fix (has_extractable_text) and both
    # markdownify-reporting tests run everywhere.
    @pytest.mark.skipif(
        not READABILITY_AVAILABLE,
        reason="readability-lxml not installed; its empty-verdict branch is unreachable",
    )
    def test_empty_verdict_falls_back_to_raw_document(self):
        """readability returning an empty body must not yield empty content."""
        thin = "<html><body><p>Hi.</p></body></html>"

        with patch(
            "opp.extractors.html.markdown_converter.readability.Document"
        ) as mock_doc:
            mock_doc.return_value.summary.return_value = (
                '<body id="readabilityBody">\n\n</body>'
            )
            result = extract_with_readability(thin)

        assert result == strip_scripts_and_styles(thin)
        assert "Hi." in result, "text was lost instead of falling back"

    @pytest.mark.skipif(
        not READABILITY_AVAILABLE,
        reason="readability-lxml not installed; nothing routes through it",
    )
    def test_real_content_still_goes_through_readability(self):
        """The fallback must not fire when readability returns real content."""
        rich = "<html><body><h1>Test</h1><p>Hello, world.</p></body></html>"
        summary = extract_with_readability(rich)

        assert 'id="readabilityBody"' in summary
        assert "Hello, world." in summary

    def test_pdf2html_keeps_single_line_document(self, tmp_path: Path):
        """A one-page PDF must keep its text (regression for the 12 matrix cells)."""
        fitz = pytest.importorskip("fitz")

        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "Hello, world.")
        pdf_path = tmp_path / "thin.pdf"
        doc.save(str(pdf_path))
        doc.close()

        from opp.extractors.pdf2html import PDF2HTMLExtractor

        result = PDF2HTMLExtractor().extract(pdf_path)

        assert result.paragraphs, "single-line PDF lost all its text"
        assert "Hello, world." in result.content
        # Still reported as a PDF, so the PDF→XLIFF guard keeps firing.
        assert result.metadata is not None
        assert result.metadata.format_type == "pdf"


# ── (b) a missing markdownify must announce itself ──────────────────


class TestMissingMarkdownifyIsReported:
    def _html(self, tmp_path: Path) -> Path:
        f = tmp_path / "sample.html"
        f.write_text(
            "<!DOCTYPE html><html><body><h1>Test</h1>"
            "<p>Hello, world.</p></body></html>",
            encoding="utf-8",
        )
        return f

    def test_extract_warns_when_markdownify_missing(self, tmp_path: Path):
        with patch("opp.extractors.html.MARKDOWNIFY_AVAILABLE", False):
            result = HTMLExtractor().extract(self._html(tmp_path))

        assert any("markdownify" in w for w in result.warnings), (
            f"missing markdownify must be named in warnings, got {result.warnings}"
        )

    def test_no_spurious_warning_when_markdownify_present(self, tmp_path: Path):
        with patch("opp.extractors.html.MARKDOWNIFY_AVAILABLE", True):
            result = HTMLExtractor().extract(self._html(tmp_path))

        assert not any("markdownify" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_capabilities_report_degradation(self):
        # `opp.mcp.tools` re-exports the function under the same name as the
        # submodule, so the module has to be resolved explicitly — a plain
        # `from opp.mcp.tools import get_capabilities` binds the function and
        # has no MARKDOWNIFY_AVAILABLE attribute to patch.
        cap = import_module("opp.mcp.tools.get_capabilities")

        with patch.object(cap, "MARKDOWNIFY_AVAILABLE", False):
            degraded = await cap.get_capabilities()
        assert any(
            "markdownify" in d for d in degraded["content"]["degradations"]
        ), degraded["content"]["degradations"]

        with patch.object(cap, "MARKDOWNIFY_AVAILABLE", True):
            healthy = await cap.get_capabilities()
        assert healthy["content"]["degradations"] == []


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))