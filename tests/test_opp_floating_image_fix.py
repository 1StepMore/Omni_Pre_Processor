"""Tests for floating image extraction (wp:anchor) and coordinate parsing.

Phase 2 of the nightly-test work: OPP must distinguish floating (wp:anchor)
drawings from inline (wp:inline) drawings and carry positionH/positionV EMU
offsets so that downstream ORF can reinject wp:anchor elements when
backfilling the DOCX from MD.

Coverage:
  1. ``_extract_anchor_offsets`` helper — wp:anchor with posOffset,
     wp:align only, no anchor at all, and missing positionH/positionV.
  2. ``ImageData`` dataclass defaults — new fields exist and default
     to (False, 0, 0) for backward compatibility with inline images.
  3. ``images_json.generate_images_json`` — carries is_floating /
     wp_anchor_h / wp_anchor_v through to the JSON output only when
     the image is floating (gating preserves the previous JSON shape
     for inline images).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from lxml import etree


# ----------------------------------------------------------------------------
# Namespace constants (mirror src/opp/extractors/docx.py)
# ----------------------------------------------------------------------------
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_MAP = {"w": W_NS, "wp": WP_NS}


# ----------------------------------------------------------------------------
# 1. _extract_anchor_offsets helper
# ----------------------------------------------------------------------------
class TestExtractAnchorOffsets:
    """Unit tests for the module-level ``_extract_anchor_offsets`` helper."""

    def test_returns_zero_zero_for_inline_drawing(self):
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:inline>
                <wp:extent cx="100" cy="100"/>
              </wp:inline>
            </w:drawing>
        """)
        assert _extract_anchor_offsets(drawing, WP_NS, NS_MAP) == (0, 0)

    def test_extracts_pos_offset_emu_values(self):
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:anchor distT="0" distB="0" distL="114300" distR="114300"
                         simplePos="0" relativeHeight="251660288" behindDoc="0"
                         locked="0" layoutInCell="1" allowOverlap="1">
                <wp:simplePos x="0" y="0"/>
                <wp:positionH relativeFrom="page">
                  <wp:posOffset>914400</wp:posOffset>
                </wp:positionH>
                <wp:positionV relativeFrom="page">
                  <wp:posOffset>1828800</wp:posOffset>
                </wp:positionV>
              </wp:anchor>
            </w:drawing>
        """)
        h, v = _extract_anchor_offsets(drawing, WP_NS, NS_MAP)
        # 914400 EMU = 1 inch horizontal, 1828800 EMU = 2 inches vertical
        assert h == 914400
        assert v == 1828800

    def test_returns_zero_when_anchor_uses_align_not_posoffset(self):
        """wp:align keywords (left/center/right) are not numeric offsets."""
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:anchor>
                <wp:positionH relativeFrom="page">
                  <wp:align>center</wp:align>
                </wp:positionH>
                <wp:positionV relativeFrom="page">
                  <wp:align>top</wp:align>
                </wp:positionV>
              </wp:anchor>
            </w:drawing>
        """)
        assert _extract_anchor_offsets(drawing, WP_NS, NS_MAP) == (0, 0)

    def test_returns_zero_when_position_elements_missing(self):
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:anchor>
                <wp:simplePos x="0" y="0"/>
              </wp:anchor>
            </w:drawing>
        """)
        assert _extract_anchor_offsets(drawing, WP_NS, NS_MAP) == (0, 0)

    def test_handles_non_numeric_posoffset_text(self):
        """Malformed posOffset text falls back to 0 instead of raising."""
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:anchor>
                <wp:positionH relativeFrom="page">
                  <wp:posOffset>not-a-number</wp:posOffset>
                </wp:positionH>
                <wp:positionV relativeFrom="page">
                  <wp:posOffset>   </wp:posOffset>
                </wp:positionV>
              </wp:anchor>
            </w:drawing>
        """)
        assert _extract_anchor_offsets(drawing, WP_NS, NS_MAP) == (0, 0)

    def test_partial_anchor_only_horizontal(self):
        """If only positionH is present, positionV defaults to 0."""
        from opp.extractors.docx import _extract_anchor_offsets

        drawing = etree.fromstring(f"""
            <w:drawing xmlns:w="{W_NS[1:-1]}" xmlns:wp="{WP_NS[1:-1]}">
              <wp:anchor>
                <wp:positionH relativeFrom="page">
                  <wp:posOffset>500000</wp:posOffset>
                </wp:positionH>
              </wp:anchor>
            </w:drawing>
        """)
        assert _extract_anchor_offsets(drawing, WP_NS, NS_MAP) == (500000, 0)


# ----------------------------------------------------------------------------
# 2. ImageData dataclass defaults
# ----------------------------------------------------------------------------
class TestImageDataFloatingFields:
    """``ImageData`` must accept the new fields with safe defaults."""

    def test_defaults_are_backward_compatible(self):
        from opp.utils.dataclasses import ImageData

        img = ImageData(data=b"", mime_type="image/png")
        assert img.is_floating is False
        assert img.wp_anchor_h == 0
        assert img.wp_anchor_v == 0
        # Existing fields still default to None
        assert img.paragraph_index is None

    def test_floating_fields_are_settable(self):
        from opp.utils.dataclasses import ImageData

        img = ImageData(
            data=b"x",
            mime_type="image/png",
            is_floating=True,
            wp_anchor_h=914400,
            wp_anchor_v=1828800,
        )
        assert img.is_floating is True
        assert img.wp_anchor_h == 914400
        assert img.wp_anchor_v == 1828800


# ----------------------------------------------------------------------------
# 3. images_json.py carries floating metadata
# ----------------------------------------------------------------------------
class TestImagesJsonFloatingPropagation:
    """``images.json`` must expose is_floating / wp_anchor_h / wp_anchor_v
    only for floating images; inline images keep the previous shape."""

    def _make_extraction_result(self, images):
        from opp.utils.dataclasses import DocumentMetadata, ExtractionResult

        meta = DocumentMetadata(
            file_path="/tmp/x.docx",
            original_filename="x.docx",
            format="DOCX",
            file_size_bytes=0,
            file_hash_md5="0" * 32,
        )
        return ExtractionResult(
            paragraphs=[],
            tables=[],
            images=images,
            metadata=meta,
            warnings=[],
        )

    def test_inline_image_json_omits_floating_fields(self, tmp_path: Path):
        from opp.utils.dataclasses import ImageData
        from opp.utils.images_json import generate_images_json

        img = ImageData(
            data=b"\x89PNG\r\n",
            mime_type="image/png",
            paragraph_index=3,
            is_floating=False,
        )
        out_path = tmp_path / "images.json"
        result = generate_images_json(self._make_extraction_result([img]), out_path)

        assert result["images"][0]["paragraph_index"] == 3
        assert "is_floating" not in result["images"][0]
        assert "wp_anchor_h" not in result["images"][0]
        assert "wp_anchor_v" not in result["images"][0]

    def test_floating_image_json_includes_anchor_fields(self, tmp_path: Path):
        from opp.utils.dataclasses import ImageData
        from opp.utils.images_json import generate_images_json

        img = ImageData(
            data=b"\x89PNG\r\n",
            mime_type="image/png",
            paragraph_index=None,  # floating images have no paragraph index
            is_floating=True,
            wp_anchor_h=914400,
            wp_anchor_v=1828800,
        )
        out_path = tmp_path / "images.json"
        result = generate_images_json(self._make_extraction_result([img]), out_path)

        entry = result["images"][0]
        assert entry["is_floating"] is True
        assert entry["wp_anchor_h"] == 914400
        assert entry["wp_anchor_v"] == 1828800
        assert entry["paragraph_index"] is None

    def test_floating_image_with_zero_anchor_omits_anchor_keys(self, tmp_path: Path):
        """If anchor offsets are 0 (align-only or missing), keys are omitted
        to keep the JSON shape minimal — ORF treats absence as 'unspecified'."""
        from opp.utils.dataclasses import ImageData
        from opp.utils.images_json import generate_images_json

        img = ImageData(
            data=b"\x89PNG\r\n",
            mime_type="image/png",
            is_floating=True,
            wp_anchor_h=0,
            wp_anchor_v=0,
        )
        out_path = tmp_path / "images.json"
        result = generate_images_json(self._make_extraction_result([img]), out_path)

        entry = result["images"][0]
        assert entry["is_floating"] is True
        assert "wp_anchor_h" not in entry
        assert "wp_anchor_v" not in entry
