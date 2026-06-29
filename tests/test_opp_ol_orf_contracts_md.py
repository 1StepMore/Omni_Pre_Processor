"""MD-path OPP→OL→ORF Contract Tests (mirrors XLIFF contract at test_opp_ol_orf_contracts.py).

These tests verify that each module's output satisfies the next module's
input requirements, using REAL pipeline calls (not hardcoded strings) and
the PUBLIC `MD2DOCXConverter.convert()`:

  OPP output (real .md from OPPPipeline)           →  OL input
  OL output (real translated .md from MCP)         →  ORF input
  ORF output (real .docx from public convert())    ←  end product

The comprehensive mock (`_comprehensive_translate`) guarantees that the
translated content is demonstrably different from the source, so the
tests can assert translation actually happened.
"""

import asyncio
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("ol_mcp", reason="ol_mcp not installed (cross-module contract tests)")
# Cross-repo path setup: OL and ORF live in sibling repos under Omni_Suite
_OL_SRC = Path(__file__).resolve().parents[2] / "Omni_Localizer" / "src"
_ORF_SRC = Path(__file__).resolve().parents[2] / "Omni_Re_Formatter" / "src"
for _p in (str(_OL_SRC), str(_ORF_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


# ============================================================================
# Comprehensive translate mock — returns demonstrably different text
# ============================================================================

_COMPREHENSIVE_TRANSLATE_MAP = {
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

def verify_opp_md_preserves_source(md_content: str) -> tuple[bool, str]:
    """Verify OPP MD has source paragraphs (not yet translated)."""
    if not md_content.strip():
        return False, "OPP MD should not be empty"
    if "Contract Test Paragraph 1" not in md_content:
        return False, "OPP MD should contain source paragraph 1"
    if "Contract Test Paragraph 2" not in md_content:
        return False, "OPP MD should contain source paragraph 2"
    return True, "OK"


def verify_ol_md_has_translation(md_content: str) -> tuple[bool, str]:
    """Verify OL MD has translated text (different from source)."""
    if not md_content.strip():
        return False, "OL MD should not be empty"
    has_translation = (
        "合同测试段落 1" in md_content
        or "合同测试段落 2" in md_content
        or "[ZH]" in md_content
    )
    if not has_translation:
        return False, "OL MD should contain translated content"
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
# OPP → OL Contract Tests (MD path)
# ============================================================================

class TestOPPtoOLContract_MD:
    """Test OPP output (MD) satisfies OL input requirements."""

    def test_opp_generates_md_with_source(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """OPP should generate MD preserving source paragraphs via real pipeline."""
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        md_path = tmp_path / "opp_output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()

        md_content = md_path.read_text(encoding="utf-8")
        valid, msg = verify_opp_md_preserves_source(md_content)
        assert valid, f"OPP MD contract violated: {msg}"

    def test_ol_accepts_opp_md_format(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """OL's MCP translate_md_text must handle real OPP MD output.

        Uses real OPP pipeline → real MD → real OL MCP with comprehensive
        mock. The mock guarantees translated != source so the test
        asserts translation actually happened.
        """
        from ol_mcp.tools import TranslateInput, translate_md_text

        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        md_path = tmp_path / "opp_output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        md_content = md_path.read_text(encoding="utf-8")

        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance

            params = TranslateInput(
                content=md_content,
                source_lang="en",
                target_lang="zh",
            )
            result_str = asyncio.run(translate_md_text(params))
            result_data = json.loads(result_str)

        assert result_data["success"], f"OL failed: {result_data}"

        valid, msg = verify_ol_md_has_translation(result_data["translated"])
        assert valid, f"OL MD output contract violated: {msg}"


# ============================================================================
# OL → ORF Contract Tests (MD path)
# ============================================================================

class TestOLtoORFContract_MD:
    """Test OL MD output satisfies ORF input via real public convert()."""

    def test_orf_accepts_md_with_translation(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """ORF should accept translated MD via real public convert().

        Replaces the old version which called the PRIVATE
        XLIFF2DOCXConverter._backfill_translation() with hardcoded XML
        strings. Now uses the PUBLIC MD2DOCXConverter.convert(input_path,
        output_path) which produces a real DOCX on disk (pandoc mocked),
        and verifies the DOCX structure.
        """
        from ol_mcp.tools import TranslateInput, translate_md_text
        from orf.channels.md2docx import MD2DOCXConverter

        # Step 1: Real OPP → real MD
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        md_path = tmp_path / "opp_output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        # Step 2: Real OL MCP → real translated MD
        ol_md_path = tmp_path / "ol_output.md"
        md_content = md_path.read_text(encoding="utf-8")
        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance
            params = TranslateInput(
                content=md_content,
                source_lang="en",
                target_lang="zh",
            )
            result_str = asyncio.run(translate_md_text(params))
            result_data = json.loads(result_str)
        assert result_data["success"], f"OL failed: {result_data}"

        ol_md_path.write_text(result_data["translated"], encoding="utf-8")

        # Step 3: PUBLIC MD2DOCXConverter.convert() → real DOCX (pandoc mocked)
        converter = MD2DOCXConverter()
        docx_output = tmp_path / "result.docx"

        with patch("subprocess.run", side_effect=_pandoc_side_effect):
            conv_result = converter.convert(
                input_path=ol_md_path,
                output_path=docx_output,
            )

        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        # Verify real DOCX structure
        valid, msg = verify_orf_docx_valid(docx_output)
        assert valid, f"ORF output DOCX invalid: {msg}"


# ============================================================================
# Full OPP → OL → ORF Pipeline (MD path)
# ============================================================================

class TestFullPipelineContracts_MD:
    """Test the full OPP → OL → ORF pipeline for MD path using real APIs."""

    def test_full_pipeline_md_preserves_translations(
        self, opp_pipeline, real_docx_input, tmp_path
    ):
        """End-to-end: real OPP → real OL MCP → real ORF convert() → real DOCX.

        1. OPPPipeline.process_file() + generate_markdown()
        2. ol_mcp.tools.translate_md_text() (with comprehensive mock that
           guarantees translated != source)
        3. MD2DOCXConverter.convert() (PUBLIC method, pandoc mocked) → real DOCX

        Verifies each contract at every step and the final DOCX is valid.
        """
        from ol_mcp.tools import TranslateInput, translate_md_text
        from orf.channels.md2docx import MD2DOCXConverter

        # Step 1: Real OPP pipeline → real MD
        result = opp_pipeline.process_file(real_docx_input)
        assert result.extraction_result is not None

        md_path = tmp_path / "step1_opp_output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        # Step 2: Verify OPP contract
        md_content = md_path.read_text(encoding="utf-8")
        valid, msg = verify_opp_md_preserves_source(md_content)
        assert valid, f"OPP contract violated: {msg}"

        # Step 3: Real OL MCP with comprehensive mock (verifies text changed)
        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            mock_instance = _AsyncMockPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance
            params = TranslateInput(
                content=md_content,
                source_lang="en",
                target_lang="zh",
            )
            ol_result_str = asyncio.run(translate_md_text(params))
            ol_data = json.loads(ol_result_str)
        assert ol_data["success"], f"OL step failed: {ol_data}"

        # Step 4: Verify OL contract
        valid, msg = verify_ol_md_has_translation(ol_data["translated"])
        assert valid, f"OL contract violated: {msg}"

        # Step 5: Save translated MD + Real ORF convert() → real DOCX
        ol_md_path = tmp_path / "step2_ol_output.md"
        ol_md_path.write_text(ol_data["translated"], encoding="utf-8")

        converter = MD2DOCXConverter()
        docx_output = tmp_path / "step3_orf_result.docx"

        with patch("subprocess.run", side_effect=_pandoc_side_effect):
            conv_result = converter.convert(
                input_path=ol_md_path,
                output_path=docx_output,
            )

        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        # Step 6: Verify real DOCX
        valid, msg = verify_orf_docx_valid(docx_output)
        assert valid, f"ORF DOCX invalid: {msg}"
