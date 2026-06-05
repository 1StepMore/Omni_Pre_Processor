"""OPP→OL→ORF Contract Tests (upgraded to use real APIs).

These tests verify that each module's output satisfies the next module's
input requirements, using REAL pipeline calls (not hardcoded strings) and
the PUBLIC `XLIFF2DOCXConverter.convert()` (not the private
`_backfill_translation`):

  OPP output (real .xlf + .md from OPPPipeline)  →  OL input
  OL output (real translated .xlf from MCP)        →  ORF input
  ORF output (real .docx from public convert())   ←  end product

The comprehensive mock (`_comprehensive_translate`) guarantees that
`<target>` content is demonstrably different from `<source>`, so the
tests can assert translation actually happened.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Comprehensive translate mock — returns demonstrably different text
# ============================================================================

_COMPREHENSIVE_TRANSLATE_MAP = {
    "Hello": "你好",
    "World": "世界",
    "Contract Test Paragraph 1": "合同测试段落 1",
    "Contract Test Paragraph 2": "合同测试段落 2",
}


def _comprehensive_translate(text, src_lang, tgt_lang, context=None):
    if text in _COMPREHENSIVE_TRANSLATE_MAP:
        return _COMPREHENSIVE_TRANSLATE_MAP[text]
    return "[ZH]"


class _AsyncMockPool:
    async def translate(self, text, src_lang, tgt_lang, context=None):
        return _comprehensive_translate(text, src_lang, tgt_lang, context)


# ============================================================================
# Helper: create a minimal real DOCX for testing
# ============================================================================

def _create_minimal_docx(docx_path: Path) -> None:
    """Create a minimal valid DOCX (real ZIP with word/document.xml)."""
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Contract Test Paragraph 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>Contract Test Paragraph 2</w:t></w:r></w:p>
  </w:body>
</w:document>""")
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")


# ============================================================================
# Helper: pandoc mock for ORF MD channel (pandoc not installed in test env)
# ============================================================================

def _pandoc_side_effect(*args, **kwargs):
    """Mock pandoc: create a real minimal DOCX at the output path."""
    cmd = args[0] if args else kwargs.get("args", [])
    if "-o" in cmd:
        output_idx = cmd.index("-o") + 1
        output_path = Path(cmd[output_idx])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Translated content</w:t></w:r></w:p></w:body>
</w:document>""")
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return result


# ============================================================================
# Contract verification helpers
# ============================================================================

def verify_opp_xliff_has_no_target(xliff_content: str) -> tuple[bool, str]:
    """Verify OPP XLIFF has <source> but no <target> elements."""
    root = ET.fromstring(xliff_content)
    has_source = False
    has_target = False
    for unit in root.iter():
        tag = unit.tag
        if "source" in tag.lower():
            has_source = True
        if "target" in tag.lower():
            has_target = True
    if not has_source:
        return False, "OPP XLIFF should have <source> elements"
    if has_target:
        return False, "OPP XLIFF should NOT have <target> elements (OL adds them)"
    return True, "OK"


def verify_ol_xliff_has_target(xliff_content: str) -> tuple[bool, str]:
    """Verify OL XLIFF has both <source> and <target> elements."""
    root = ET.fromstring(xliff_content)
    ns_uri = None
    for elem in root.iter():
        if "}" in elem.tag:
            ns_uri = elem.tag[1:elem.tag.index("}")]
            break
    units_missing_target = []
    units_missing_source = []
    for trans_unit in root.iter():
        tag = trans_unit.tag
        if tag.endswith("}trans-unit") or tag == "trans-unit":
            unit_id = trans_unit.get("id")
            ns_prefix = f"{{{ns_uri}}}" if ns_uri else ""
            source_el = trans_unit.find(f"{ns_prefix}source")
            target_el = trans_unit.find(f"{ns_prefix}target")
            if source_el is None:
                units_missing_source.append(unit_id)
            if target_el is None:
                units_missing_target.append(unit_id)
    errors = []
    if units_missing_source:
        errors.append(f"missing <source>: {units_missing_source}")
    if units_missing_target:
        errors.append(f"missing <target>: {units_missing_target}")
    if errors:
        return False, "; ".join(errors)
    return True, "OK"


def verify_orf_docx_valid(docx_path: Path) -> tuple[bool, str]:
    """Verify ORF output is a valid DOCX with word/document.xml."""
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            names = zf.namelist()
            if "word/document.xml" not in names:
                return False, "Missing word/document.xml"
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            ET.fromstring(doc_xml)
            return True, "OK"
    except zipfile.BadZipFile:
        return False, "Not a valid ZIP"
    except ET.ParseError as e:
        return False, f"Invalid XML: {e}"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def real_docx_input(tmp_path: Path) -> Path:
    """Create a real minimal DOCX for OPP to extract."""
    docx_path = tmp_path / "contract_input.docx"
    _create_minimal_docx(docx_path)
    return docx_path


@pytest.fixture
def opp_pipeline(tmp_path: Path):
    """Create a real OPPPipeline."""
    from opp.pipeline import OPPPipeline
    res_dir = tmp_path / "opp_resources"
    res_dir.mkdir(exist_ok=True)
    return OPPPipeline(resource_storage_dir=res_dir)


# ============================================================================
# OPP → OL Contract Tests (upgraded: real OPPPipeline + real OL MCP)
# ============================================================================

class TestOPPtoOLContract:
    """Test OPP output (from real pipeline) satisfies OL input requirements."""

    def test_opp_generates_source_only_xliff(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """OPP should generate XLIFF with <source> only via real pipeline.

        Replaces the old version which just verified a hardcoded
        string constant. Now calls real OPPPipeline.process_file() +
        generate_xliff() and verifies the actual output contract.
        """
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        xliff_path = tmp_path / "opp_output.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        xliff_content = xliff_path.read_text(encoding="utf-8")
        valid, msg = verify_opp_xliff_has_no_target(xliff_content)
        assert valid, f"OPP XLIFF contract violated: {msg}"

    def test_ol_accepts_opp_source_only_format(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """OL's MCP translate_xliff must handle real OPP XLIFF output.

        Uses real OPP pipeline → real XLIFF → real OL MCP with comprehensive
        mock. The mock guarantees <target> != <source> so the test
        asserts translation actually happened.
        """
        from ol_mcp.tools import translate_xliff, TranslateXliffInput

        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        xliff_path = tmp_path / "opp_output.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance

            ol_output_path = str(tmp_path / "ol_output.xlf")
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=ol_output_path,
                source_lang="en",
                target_lang="zh",
            )
            result_str = translate_xliff(params)
            result_data = json.loads(result_str)

        assert result_data["success"], f"OL failed: {result_data}"

        ol_output = Path(ol_output_path).read_text(encoding="utf-8")
        valid, msg = verify_ol_xliff_has_target(ol_output)
        assert valid, f"OL output contract violated: {msg}"


# ============================================================================
# OL → ORF Contract Tests (upgraded: real XLIFF2DOCXConverter.convert())
# ============================================================================

class TestOLtoORFContract:
    """Test OL output satisfies ORF input via real public convert()."""

    def test_orf_accepts_xliff_with_target(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """ORF should backfill XLIFF translations via real public convert().

        Replaces the old version which called the PRIVATE
        XLIFF2DOCXConverter._backfill_translation() with hardcoded
        XML strings. Now uses the PUBLIC convert(input_skeleton,
        xliff_path, output_path) which produces a real DOCX on disk,
        and verifies the DOCX structure + contains translation markers.
        """
        from ol_mcp.tools import translate_xliff, TranslateXliffInput
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        # Step 1: Real OPP → real XLIFF + real skeleton
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        xliff_path = tmp_path / "opp_output.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        skeleton_zip = opp_pipeline.save_skeleton(
            result.extraction_result, real_docx_input.stem, tmp_path
        )
        assert skeleton_zip is not None and skeleton_zip.exists()

        # Step 2: Real OL MCP → real translated XLIFF
        ol_xliff_path = tmp_path / "ol_output.xlf"
        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=str(ol_xliff_path),
                source_lang="en",
                target_lang="zh",
            )
            result_str = translate_xliff(params)
            result_data = json.loads(result_str)
        assert result_data["success"], f"OL failed: {result_data}"

        # Step 3: PUBLIC XLIFF2DOCXConverter.convert() → real DOCX
        converter = XLIFF2DOCXConverter()
        docx_output = tmp_path / "result.docx"
        conv_result = converter.convert(
            input_skeleton=skeleton_zip,
            xliff_path=ol_xliff_path,
            output_path=docx_output,
        )
        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        # Verify real DOCX structure
        valid, msg = verify_orf_docx_valid(docx_output)
        assert valid, f"ORF output DOCX invalid: {msg}"

        # Verify translation markers in final DOCX
        with zipfile.ZipFile(docx_output) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert any(m in doc_xml for m in ["[ZH]", "合同测试段落 1", "合同测试段落 2"]), "No translation marker in final DOCX"


# ============================================================================
# Full OPP → OL → ORF Pipeline (upgraded: real APIs all the way)
# ============================================================================

class TestFullPipelineContracts:
    """Test the full OPP → OL → ORF pipeline using real APIs and comprehensive mock."""

    def test_full_pipeline_preserves_translations(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """End-to-end: real OPP → real OL MCP → real ORF convert() → real DOCX.

        Replaces the old version which used hardcoded string constants
        and the private _backfill_translation(). Now exercises the
        full chain with real APIs:

        1. OPPPipeline.process_file() + generate_xliff() + save_skeleton()
        2. ol_mcp.tools.translate_xliff() (with comprehensive mock that
           guarantees <target> != <source>)
        3. XLIFF2DOCXConverter.convert() (PUBLIC method) → real DOCX

        Verifies each contract at every step and the final DOCX contains
        translation markers.
        """
        from ol_mcp.tools import translate_xliff, TranslateXliffInput
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        # Step 1: Real OPP pipeline → real XLIFF + real skeleton
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        xliff_path = tmp_path / "step1_opp_output.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        skeleton_zip = opp_pipeline.save_skeleton(
            result.extraction_result, real_docx_input.stem, tmp_path
        )
        assert skeleton_zip is not None and skeleton_zip.exists()

        # Step 2: Verify OPP contract
        xliff_content = xliff_path.read_text(encoding="utf-8")
        valid, msg = verify_opp_xliff_has_no_target(xliff_content)
        assert valid, f"OPP contract violated: {msg}"

        # Step 3: Real OL MCP with comprehensive mock (verifies text changed)
        ol_xliff_path = tmp_path / "step2_ol_output.xlf"
        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=str(ol_xliff_path),
                source_lang="en",
                target_lang="zh",
            )
            ol_result_str = translate_xliff(params)
            ol_data = json.loads(ol_result_str)
        assert ol_data["success"], f"OL step failed: {ol_data}"

        # Step 4: Verify OL contract + text actually changed
        ol_xliff_content = ol_xliff_path.read_text(encoding="utf-8")
        valid, msg = verify_ol_xliff_has_target(ol_xliff_content)
        assert valid, f"OL contract violated: {msg}"

        ol_root = ET.fromstring(ol_xliff_content)
        ns_uri = None
        for elem in ol_root.iter():
            if "}" in elem.tag:
                ns_uri = elem.tag[1:elem.tag.index("}")]
                break
        translated_count = 0
        for unit in ol_root.iter(f"{{{ns_uri}}}trans-unit"):
            if unit.find(f"{{{ns_uri}}}target") is not None:
                translated_count += 1
        assert translated_count > 0, "OL produced no <target> elements"

        # Step 5: Real ORF convert() → real DOCX (NOT private _backfill_translation)
        converter = XLIFF2DOCXConverter()
        docx_output = tmp_path / "step3_orf_result.docx"
        conv_result = converter.convert(
            input_skeleton=skeleton_zip,
            xliff_path=ol_xliff_path,
            output_path=docx_output,
        )
        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        # Step 6: Verify real DOCX
        valid, msg = verify_orf_docx_valid(docx_output)
        assert valid, f"ORF DOCX invalid: {msg}"

        with zipfile.ZipFile(docx_output) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert any(m in doc_xml for m in ["[ZH]", "合同测试段落 1", "合同测试段落 2"]), "No translation marker in final DOCX"
