"""Unit tests for OPP DOCX helper functions.

Tests for the pure/module-level helper functions in docx.py:
  - _parse_position_value — reads EMU offset from wp:positionH/V
  - _extract_anchor_offsets — extracts (H, V) offsets from wp:anchor
  - _walk_table_paragraphs   — recovers paragraphs inside w:tbl
  - _walk_textbox_paragraphs — recovers paragraphs inside w:txbxContent
  - _is_chinese_heading / _detect_chinese_heading_level

These tests use fabricated lxml elements — no real DOCX files needed.
"""

from lxml import etree

from opp.extractors.docx import (
    _parse_position_value,
    _extract_anchor_offsets,
    DOCXExtractor,
)

# ── Namespace constants (mirror those used in docx.py) ──────────────────
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
# Clark notation versions (with curly braces) for lxml search functions
W_NS_CLARK = f"{{{W_NS}}}"
WP_NS_CLARK = f"{{{WP_NS}}}"
A_NS_CLARK = f"{{{A_NS}}}"
WP_NS_MAP = {"wp": WP_NS_CLARK}


# ══════════════════════════════════════════════════════════════════════
# _parse_position_value
# ══════════════════════════════════════════════════════════════════════


class TestParsePositionValue:
    """Tests for _parse_position_value()."""

    def test_none_returns_zero(self):
        """None input returns 0."""
        assert _parse_position_value(None) == 0

    def test_pos_offset_int(self):
        """Element with <wp:posOffset>12345</wp:posOffset> returns 12345."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset>12345</wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 12345

    def test_pos_offset_zero(self):
        """Element with <wp:posOffset>0</wp:posOffset> returns 0."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset>0</wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 0

    def test_large_emu_value(self):
        """Large EMU values (e.g., full-page offsets) parse correctly."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset>9144000</wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 9144000

    def test_negative_offset(self):
        """Negative EMU offsets parse correctly."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset>-914400</wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == -914400

    def test_align_keyword_returns_zero(self):
        """Element with <wp:align>center</wp:align> (no posOffset) returns 0."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:align>center</wp:align>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 0

    def test_empty_text_returns_zero(self):
        """Element with empty posOffset text returns 0."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset></wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 0

    def test_non_numeric_text_returns_zero(self):
        """Element with non-numeric posOffset text returns 0."""
        elem = etree.fromstring(
            f'<positionH xmlns:wp="{WP_NS}">'
            f'  <wp:posOffset>not-a-number</wp:posOffset>'
            f'</positionH>'
        )
        assert _parse_position_value(elem) == 0


# ══════════════════════════════════════════════════════════════════════
# _extract_anchor_offsets
# ══════════════════════════════════════════════════════════════════════


class TestExtractAnchorOffsets:
    """Tests for _extract_anchor_offsets()."""

    def test_inline_drawing_returns_zero_zero(self):
        """Inline (wp:inline) drawing without wp:anchor returns (0, 0)."""
        drawing = etree.fromstring(
            f'<w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS}">'
            f'  <wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'    <wp:extent cx="100" cy="100"/>'
            f'  </wp:inline>'
            f'</w:drawing>'
        )
        result = _extract_anchor_offsets(drawing, WP_NS_CLARK, WP_NS_MAP)
        assert result == (0, 0)

    def test_floating_with_pos_offsets(self):
        """Floating (wp:anchor) drawing returns parsed (H, V) offsets."""
        drawing = etree.fromstring(
            f'<w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS}">'
            f'  <wp:anchor>'
            f'    <wp:positionH relativeFrom="page">'
            f'      <wp:posOffset>1828800</wp:posOffset>'
            f'    </wp:positionH>'
            f'    <wp:positionV relativeFrom="page">'
            f'      <wp:posOffset>2743200</wp:posOffset>'
            f'    </wp:positionV>'
            f'    <wp:extent cx="100" cy="100"/>'
            f'  </wp:anchor>'
            f'</w:drawing>'
        )
        result = _extract_anchor_offsets(drawing, WP_NS_CLARK, WP_NS_MAP)
        assert result == (1828800, 2743200)

    def test_floating_with_align_keyword_fallback(self):
        """Floating with alignment keywords (no posOffset) returns (0, 0)."""
        drawing = etree.fromstring(
            f'<w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS}">'
            f'  <wp:anchor>'
            f'    <wp:positionH relativeFrom="page">'
            f'      <wp:align>center</wp:align>'
            f'    </wp:positionH>'
            f'    <wp:positionV relativeFrom="page">'
            f'      <wp:align>top</wp:align>'
            f'    </wp:positionV>'
            f'    <wp:extent cx="100" cy="100"/>'
            f'  </wp:anchor>'
            f'</w:drawing>'
        )
        result = _extract_anchor_offsets(drawing, WP_NS_CLARK, WP_NS_MAP)
        assert result == (0, 0)

    def test_floating_missing_pos_v(self):
        """Floating with only positionH (no positionV) returns (H, 0)."""
        drawing = etree.fromstring(
            f'<w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS}">'
            f'  <wp:anchor>'
            f'    <wp:positionH relativeFrom="page">'
            f'      <wp:posOffset>500000</wp:posOffset>'
            f'    </wp:positionH>'
            f'    <wp:extent cx="100" cy="100"/>'
            f'  </wp:anchor>'
            f'</w:drawing>'
        )
        result = _extract_anchor_offsets(drawing, WP_NS_CLARK, WP_NS_MAP)
        assert result == (500000, 0)

    def test_zero_offsets_explicit(self):
        """Floating with zero offsets returns (0, 0)."""
        drawing = etree.fromstring(
            f'<w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS}">'
            f'  <wp:anchor>'
            f'    <wp:positionH relativeFrom="page">'
            f'      <wp:posOffset>0</wp:posOffset>'
            f'    </wp:positionH>'
            f'    <wp:positionV relativeFrom="page">'
            f'      <wp:posOffset>0</wp:posOffset>'
            f'    </wp:positionV>'
            f'    <wp:extent cx="100" cy="100"/>'
            f'  </wp:anchor>'
            f'</w:drawing>'
        )
        result = _extract_anchor_offsets(drawing, WP_NS_CLARK, WP_NS_MAP)
        assert result == (0, 0)


# ══════════════════════════════════════════════════════════════════════
# _walk_textbox_paragraphs
# ══════════════════════════════════════════════════════════════════════

class TestWalkTextboxParagraphs:
    """Tests for DOCXExtractor._walk_textbox_paragraphs()."""

    def test_yields_text_from_textboxes(self):
        """Text inside w:txbxContent is yielded."""
        body = etree.fromstring(
            f'<w:body xmlns:w="{W_NS}">'
            f'  <w:p>'
            f'    <w:r>'
            f'      <w:drawing>'
            f'        <wp:inline xmlns:wp="{WP_NS}">'
            f'          <wp:extent cx="100" cy="100"/>'
            f'          <wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            f'            <wps:txbx>'
            f'              <w:txbxContent>'
            f'                <w:p><w:r><w:t>Textbox paragraph 1</w:t></w:r></w:p>'
            f'                <w:p><w:r><w:t>Textbox paragraph 2</w:t></w:r></w:p>'
            f'              </w:txbxContent>'
            f'            </wps:txbx>'
            f'          </wps:wsp>'
            f'        </wp:inline>'
            f'      </w:drawing>'
            f'    </w:r>'
            f'  </w:p>'
            f'</w:body>'
        )
        extractor = DOCXExtractor()
        results = list(extractor._walk_textbox_paragraphs(body, W_NS_CLARK))
        texts = [t for _, t in results]
        assert "Textbox paragraph 1" in texts
        assert "Textbox paragraph 2" in texts

    def test_deduplicates_identical_text(self):
        """Same text appearing in mc:Choice and mc:Fallback is yielded once."""
        body = etree.fromstring(
            f'<w:body xmlns:w="{W_NS}">'
            f'  <w:p>'
            f'    <w:r>'
            f'      <mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
            f'        <mc:Choice Requires="wps">'
            f'          <w:drawing>'
            f'            <wp:inline xmlns:wp="{WP_NS}">'
            f'              <wp:extent cx="100" cy="100"/>'
            f'              <wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            f'                <wps:txbx>'
            f'                  <w:txbxContent>'
            f'                    <w:p><w:r><w:t>Duplicate text</w:t></w:r></w:p>'
            f'                  </w:txbxContent>'
            f'                </wps:txbx>'
            f'              </wps:wsp>'
            f'            </wp:inline>'
            f'          </w:drawing>'
            f'        </mc:Choice>'
            f'        <mc:Fallback>'
            f'          <w:drawing>'
            f'            <wp:inline xmlns:wp="{WP_NS}">'
            f'              <wp:extent cx="100" cy="100"/>'
            f'              <wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            f'                <wps:txbx>'
            f'                  <w:txbxContent>'
            f'                    <w:p><w:r><w:t>Duplicate text</w:t></w:r></w:p>'
            f'                  </w:txbxContent>'
            f'                </wps:txbx>'
            f'              </wps:wsp>'
            f'            </wp:inline>'
            f'          </w:drawing>'
            f'        </mc:Fallback>'
            f'      </mc:AlternateContent>'
            f'    </w:r>'
            f'  </w:p>'
            f'</w:body>'
        )
        extractor = DOCXExtractor()
        results = list(extractor._walk_textbox_paragraphs(body, W_NS_CLARK))
        assert len(results) == 1, "Should deduplicate identical text"
        assert results[0][1] == "Duplicate text"

    def test_skips_empty_textboxes(self):
        """Empty textbox paragraphs are not yielded."""
        body = etree.fromstring(
            f'<w:body xmlns:w="{W_NS}">'
            f'  <w:p>'
            f'    <w:r>'
            f'      <w:drawing>'
            f'        <wp:inline xmlns:wp="{WP_NS}">'
            f'          <wp:extent cx="100" cy="100"/>'
            f'          <wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            f'            <wps:txbx>'
            f'              <w:txbxContent>'
            f'                <w:p><w:r><w:t></w:t></w:r></w:p>'
            f'              </w:txbxContent>'
            f'            </wps:txbx>'
            f'          </wps:wsp>'
            f'        </wp:inline>'
            f'      </w:drawing>'
            f'    </w:r>'
            f'  </w:p>'
            f'</w:body>'
        )
        extractor = DOCXExtractor()
        results = list(extractor._walk_textbox_paragraphs(body, W_NS_CLARK))
        assert results == []

    def test_no_textbox_returns_empty(self):
        """Body with no w:txbxContent yields nothing."""
        body = etree.fromstring(
            f'<w:body xmlns:w="{W_NS}">'
            f'  <w:p><w:r><w:t>No textbox here</w:t></w:r></w:p>'
            f'</w:body>'
        )
        extractor = DOCXExtractor()
        results = list(extractor._walk_textbox_paragraphs(body, W_NS_CLARK))
        assert results == []


# ══════════════════════════════════════════════════════════════════════
# _is_chinese_heading / _detect_chinese_heading_level
# ══════════════════════════════════════════════════════════════════════

class TestChineseHeadingDetection:
    """Tests for _is_chinese_heading() and _detect_chinese_heading_level()."""

    def setup_method(self) -> None:
        self.extractor = DOCXExtractor()

    def test_is_chinese_heading_returns_true(self):
        """Texts matching Chinese heading patterns return True."""
        assert self.extractor._is_chinese_heading("第一章 总论")
        assert self.extractor._is_chinese_heading("一、引言")
        assert self.extractor._is_chinese_heading("1. 概述")
        assert self.extractor._is_chinese_heading("【摘要】")
        assert self.extractor._is_chinese_heading("附录A")

    def test_is_chinese_heading_returns_false(self):
        """Regular text does not match heading patterns."""
        assert not self.extractor._is_chinese_heading("这是一个普通段落")
        assert not self.extractor._is_chinese_heading("Hello world")
        assert not self.extractor._is_chinese_heading("12345")
        assert not self.extractor._is_chinese_heading("（一）背景")  # parentheses not in patterns

    def test_detect_level_falls_back_to_3(self):
        """Non-heading text falls through to level 3 (not None)."""
        assert self.extractor._detect_chinese_heading_level("普通文本") == 3

    def test_detect_level_for_numbered_headings(self):
        """Numbered headings return the correct level."""
        # 第X章 → level 1
        assert self.extractor._detect_chinese_heading_level("第一章 总论") == 1
        # 一、 → level 2
        assert self.extractor._detect_chinese_heading_level("一、引言") == 2
        # 1. → level 3 (fallthrough — no specific pattern, but _is_chinese_heading matches)
        assert self.extractor._detect_chinese_heading_level("1. 概述") == 3
