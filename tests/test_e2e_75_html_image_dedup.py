"""E2E-75 regression tests.

The bug: ``HTMLExtractor._extract_images`` returned images with
``element_index`` but no ``paragraph_index``, while
``MarkdownGenerator.generate`` keyed its paragraph-level image injection
off ``para.para_index_in_body``. The two never matched, so every HTML
image was treated as "orphaned" and dumped into a trailing
``## Images`` block — even though ``_html_to_markdown`` (via
markdownify) had already written the ``![alt](src)`` ref inline in the
paragraph text. Pandoc then embedded each image TWICE in the output
DOCX (once inline, once from the trailing section).

The fix adds an ``is_inline_in_md`` flag on ``ImageData`` that
``MarkdownGenerator`` respects: when the flag is set, the generator
skips both its own inline injection and the ``## Images`` block.
``HTMLExtractor._extract_images`` now sets the flag for every image
because every HTML image is already inline in the markdown.
"""
from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

import pytest

from opp.extractors.html import HTMLExtractor
from opp.markdown.generator import MarkdownGenerator
from opp.utils.dataclasses import ImageData, ParagraphData


def _make_png() -> bytes:
    """1×1 transparent PNG (smallest valid PNG)."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(
            ">I", zlib.crc32(t + d) & 0xFFFFFFFF
        )
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    raw = b"\x00\x00\x00\x00\x00"
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture
def html_with_local_images(tmp_path: Path) -> Path:
    """HTML with three local-image <img> tags and three paragraphs."""
    for name in ("pic1.png", "pic2.png", "pic3.png"):
        (tmp_path / name).write_bytes(_make_png())
    html = """<html><body>
<h1>Title</h1>
<p>Para 1 with <img src="pic1.png" alt="img1"/> image.</p>
<p>Para 2 with <img src="pic2.png" alt="img2"/> another image.</p>
<p>Para 3 with <img src="pic3.png" alt="img3"/> image.</p>
</body></html>"""
    p = tmp_path / "test.html"
    p.write_text(html, encoding="utf-8")
    return p


class TestHtmlExtractorSetsInlineFlag:
    """``_extract_images`` must flag every image as inline-in-md."""

    def test_local_image_is_marked_inline(self, html_with_local_images: Path):
        result = HTMLExtractor().extract(html_with_local_images)
        assert len(result.images) == 3, (
            f"Expected 3 images, got {len(result.images)}"
        )
        for img in result.images:
            assert img.is_inline_in_md is True, (
                f"HTML image (element_index={img.element_index}) must be "
                f"marked is_inline_in_md=True so the generator skips "
                f"re-injection"
            )


class TestMarkdownGeneratorSkipsInlineImages:
    """``MarkdownGenerator.generate`` must not double-emit inline images."""

    def test_no_trailing_images_section_for_html(self, html_with_local_images: Path):
        result = HTMLExtractor().extract(html_with_local_images)
        md = MarkdownGenerator().generate(result)
        assert "## Images" not in md, (
            f"## Images trailing block must not appear for HTML input — the "
            f"image refs are already inline in the markdown. Got:\n{md}"
        )

    def test_no_duplicate_image_refs(self, html_with_local_images: Path):
        """Each image must appear at most once in the final markdown."""
        result = HTMLExtractor().extract(html_with_local_images)
        md = MarkdownGenerator().generate(result)
        # Count image refs. Each of the 3 local PNGs is referenced once
        # by markdownify. After the fix, the generator must NOT re-emit
        # them, so the total should be exactly 3 (one per paragraph).
        for name in ("pic1.png", "pic2.png", "pic3.png"):
            assert md.count(name) == 1, (
                f"Image {name} should appear exactly once in the markdown "
                f"(inline in its paragraph), but found {md.count(name)} "
                f"occurrences. Got:\n{md}"
            )


class TestNonHtmlImagesUnaffected:
    """The fix must not regress DOCX-style images (no inline flag)."""

    def test_dummy_image_without_flag_is_injected_by_generator(self):
        """An ImageData WITHOUT the flag should still be injected inline
        by the generator (and end up in ``## Images`` if not matched)."""
        png_bytes = _make_png()
        result_data = {
            "paragraphs": [
                ParagraphData(text="Only paragraph", para_index_in_body=0),
            ],
            "tables": [],
            "images": [
                ImageData(
                    data=png_bytes,
                    mime_type="image/png",
                    paragraph_index=0,
                    # is_inline_in_md defaults to False
                ),
            ],
        }
        from opp.utils.dataclasses import ExtractionResult
        result = ExtractionResult(**result_data)
        md = MarkdownGenerator().generate(result)
        # Generator should write the inline ref.
        assert "![Image" in md
        assert "## Images" in md or "![Image" in md  # one or the other

    def test_explicit_inline_flag_skips_injection(self):
        """An ImageData WITH the flag set should be skipped by the generator
        even if its paragraph_index matches a paragraph."""
        png_bytes = _make_png()
        result_data = {
            "paragraphs": [
                ParagraphData(
                    text="Para with ![img1](pic1.png) already inline",
                    para_index_in_body=0,
                ),
            ],
            "tables": [],
            "images": [
                ImageData(
                    data=png_bytes,
                    mime_type="image/png",
                    paragraph_index=0,
                    is_inline_in_md=True,
                ),
            ],
        }
        from opp.utils.dataclasses import ExtractionResult
        result = ExtractionResult(**result_data)
        md = MarkdownGenerator().generate(result)
        # Generator should NOT add a second ![]() ref nor a ## Images block.
        # The paragraph text already has the ref, so the count must be 1.
        assert md.count("![img1](pic1.png)") == 1, (
            f"Generator must not duplicate an already-inline ref. Got:\n{md}"
        )
        assert "## Images" not in md, (
            f"Generator must not add ## Images block for inline images. "
            f"Got:\n{md}"
        )
