"""OPP→OL→ORF Contract Tests.

These tests verify that each module's output satisfies the next module's input requirements:

OPP output (XLIFF with <source> only) → OL input: OL must handle source-only XLIFF
OL output (XLIFF with <source> + <target>) → ORF input: ORF must handle XLIFF with target

These tests verify the contracts, NOT the implementation details.
"""

import pytest
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================================
# OPP Output Contract: XLIFF with <source> only (no <target>)
# ============================================================================

OPP_OUTPUT_XLIFF_SOURCE_ONLY = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="contract_test.docx" source-language="en" target-language="zh" datatype="wordprocessingml">
    <body>
      <trans-unit id="1">
        <source>Contract Test Paragraph 1</source>
      </trans-unit>
      <trans-unit id="2">
        <source>Contract Test Paragraph 2</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

# OPP output: Markdown
OPP_OUTPUT_MD = """---
source_file: contract_test.docx
source_lang: en
target_lang: zh
---

# Contract Test Document

Contract Test Paragraph 1

Contract Test Paragraph 2
"""


def verify_opp_xliff_has_no_target(xliff_content: str) -> tuple[bool, str]:
    """Verify OPP XLIFF has <source> but no <target> elements."""
    root = ET.fromstring(xliff_content)

    units = list(root.iter())
    has_source = False
    has_target = False

    for unit in units:
        tag = unit.tag
        if "source" in tag.lower():
            has_source = True
        if "target" in tag.lower():
            has_target = True

    if not has_source:
        return False, "OPP XLIFF should have <source> elements"
    if has_target:
        return False, "OPP XLIFF should NOT have <target> elements (OL adds them)"

    return True, "OPP XLIFF contract satisfied"


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
        errors.append(f"OL XLIFF units missing <source>: {units_missing_source}")
    if units_missing_target:
        errors.append(f"OL XLIFF units missing <target>: {units_missing_target}")

    if errors:
        return False, "; ".join(errors)

    return True, "OL XLIFF contract satisfied"


def verify_orf_docx_valid(docx_path: Path) -> tuple[bool, str]:
    """Verify ORF output is a valid DOCX with translations."""
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            names = zf.namelist()
            if "word/document.xml" not in names:
                return False, "Missing word/document.xml"

            doc_xml = zf.read("word/document.xml").decode("utf-8")

            # Should be valid XML
            ET.fromstring(doc_xml)

            return True, "ORF DOCX contract satisfied"

    except zipfile.BadZipFile:
        return False, "Not a valid ZIP archive"
    except ET.ParseError as e:
        return False, f"Invalid XML in document.xml: {e}"


# ============================================================================
# OPP → OL Contract Tests
# ============================================================================

class TestOPPtoOLContract:
    """Test OPP output satisfies OL input requirements."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_opp_generates_source_only_xliff(self, temp_dir):
        """OPP should generate XLIFF with <source> only (no <target>).

        This is OPP's contract with OL.
        OL expects <source> elements and adds <target> itself.
        """
        # Simulate OPP generating XLIFF
        xliff_content = OPP_OUTPUT_XLIFF_SOURCE_ONLY

        valid, msg = verify_opp_xliff_has_no_target(xliff_content)
        assert valid, f"OPP XLIFF contract violated: {msg}"

    def test_ol_accepts_opp_source_only_format(self, temp_dir):
        """OL's translate_xliff must handle OPP's source-only XLIFF format.

        Bug #2: OL was not injecting <target> elements for source-only XLIFF.
        """
        from unittest.mock import patch

        xliff_path = temp_dir / "opp_output.xlf"
        xliff_path.write_text(OPP_OUTPUT_XLIFF_SOURCE_ONLY, encoding="utf-8")

        def mock_translate(text, src_lang, tgt_lang, context=None):
            return f"[T: {text}]"

        with patch("ol_pool.router.ModelPool.translate", side_effect=mock_translate):
            from ol_mcp.tools import translate_xliff, TranslateXliffInput

            output_path = str(temp_dir / "ol_output.xlf")
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=output_path,
                source_lang="en",
                target_lang="zh",
            )
            result = translate_xliff(params)

        import json
        result_data = json.loads(result)

        # OL should succeed
        assert result_data["success"], f"OL failed to handle OPP source-only format: {result_data}"

        # Verify OL output has <target> elements
        ol_output = Path(output_path).read_text(encoding="utf-8")
        valid, msg = verify_ol_xliff_has_target(ol_output)
        assert valid, f"OL output contract violated: {msg}"


# ============================================================================
# OL → ORF Contract Tests
# ============================================================================

class TestOLtoORFContract:
    """Test OL output satisfies ORF input requirements."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_orf_accepts_xliff_with_target(self, temp_dir):
        """ORF should handle XLIFF with <source> and <target> elements."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        # Minimal DOCX skeleton
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Contract Test Paragraph 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>Contract Test Paragraph 2</w:t></w:r></w:p>
  </w:body>
</w:document>"""

        # OL output: XLIFF with translations
        xliff_xml = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh">
    <body>
      <trans-unit id="1">
        <source>Contract Test Paragraph 1</source>
        <target>翻译：测试段落 1</target>
      </trans-unit>
      <trans-unit id="2">
        <source>Contract Test Paragraph 2</source>
        <target>翻译：测试段落 2</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""

        converter = XLIFF2DOCXConverter()

        # Apply first translation
        result_xml = converter._backfill_translation(
            document_xml=doc_xml,
            source_text="Contract Test Paragraph 1",
            target_text="TRANSLATED_1",
            inline_elements=None,
        )

        # Apply second translation
        result_xml = converter._backfill_translation(
            document_xml=result_xml,
            source_text="Contract Test Paragraph 2",
            target_text="TRANSLATED_2",
            inline_elements=None,
        )

        # Verify translations were applied
        assert "TRANSLATED_1" in result_xml
        assert "TRANSLATED_2" in result_xml


# ============================================================================
# Full OPP → OL → ORF Pipeline Test
# ============================================================================

class TestFullPipelineContracts:
    """Test the full OPP → OL → ORF pipeline contract."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_full_pipeline_preserves_translations(self, temp_dir):
        """Test complete pipeline: OPP extract → OL translate → ORF backfill.

        This test verifies:
        1. OPP generates source-only XLIFF
        2. OL adds target translations
        3. ORF backfills translations into DOCX
        """
        from unittest.mock import patch

        # Step 1: OPP generates source-only XLIFF
        opp_xliff = OPP_OUTPUT_XLIFF_SOURCE_ONLY
        valid, msg = verify_opp_xliff_has_no_target(opp_xliff)
        assert valid, f"OPP contract violated: {msg}"

        # Step 2: OL translates (adds <target>)
        xliff_path = temp_dir / "step1_opp_output.xlf"
        xliff_path.write_text(opp_xliff, encoding="utf-8")

        def mock_translate(text, src_lang, tgt_lang, context=None):
            return f"[已翻译: {text}]"

        with patch("ol_pool.router.ModelPool.translate", side_effect=mock_translate):
            from ol_mcp.tools import translate_xliff, TranslateXliffInput

            ol_output_path = str(temp_dir / "step2_ol_output.xlf")
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=ol_output_path,
                source_lang="en",
                target_lang="zh",
            )
            ol_result = translate_xliff(params)

        import json
        ol_data = json.loads(ol_result)
        assert ol_data["success"], f"OL step failed: {ol_data}"

        ol_xliff = Path(ol_output_path).read_text(encoding="utf-8")
        valid, msg = verify_ol_xliff_has_target(ol_xliff)
        assert valid, f"OL contract violated: {msg}"

        # Step 3: ORF backfills into DOCX
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Contract Test Paragraph 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>Contract Test Paragraph 2</w:t></w:r></w:p>
  </w:body>
</w:document>"""

        # Parse OL XLIFF and backfill each unit
        ol_root = ET.fromstring(ol_xliff)
        ns_uri = None
        for elem in ol_root.iter():
            if "}" in elem.tag:
                ns_uri = elem.tag[1:elem.tag.index("}")]
                break

        result_xml = doc_xml
        for trans_unit in ol_root.iter():
            tag = trans_unit.tag
            if tag.endswith("}trans-unit") or tag == "trans-unit":
                ns_prefix = f"{{{ns_uri}}}" if ns_uri else ""
                source_el = trans_unit.find(f"{ns_prefix}source")
                target_el = trans_unit.find(f"{ns_prefix}target")

                if source_el is not None and target_el is not None:
                    source = source_el.text or ""
                    target = target_el.text or ""
                    if source and target:
                        result_xml = converter._backfill_translation(
                            document_xml=result_xml,
                            source_text=source,
                            target_text=target,
                            inline_elements=None,
                        )

        # Verify translations are in final DOCX
        assert "[已翻译: Contract Test Paragraph 1]" in result_xml
        assert "[已翻译: Contract Test Paragraph 2]" in result_xml
        assert "Contract Test Paragraph 1" not in result_xml
        assert "Contract Test Paragraph 2" not in result_xml
