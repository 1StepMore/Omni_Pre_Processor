"""Tests for XLIFFFileGenerator."""

import pytest
from pathlib import Path
import tempfile

from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit, XLIFFUnitState, XLIFFValidator


class TestXLIFFFileGenerator:
    """Test suite for XLIFFFileGenerator."""

    def test_generator_creation(self):
        """XLIFFFileGenerator can be created with attributes."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        assert gen is not None

    def test_add_unit(self):
        """Translation unit can be added."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        unit = XLIFFTransUnit(id="1", source="Hello", source_language="en")
        gen.add_unit(unit)
        assert len(gen._units) == 1

    def test_generate_xliff_bytes(self):
        """XLIFF bytes are generated."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert isinstance(xliff_bytes, bytes)
        assert len(xliff_bytes) > 0

    def test_generate_xliff_contains_source(self):
        """Generated XLIFF contains source text."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello World", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"Hello World" in xliff_bytes

    def test_generate_xliff_contains_target(self):
        """Generated XLIFF contains target text."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", target="Bonjour", source_language="en", target_language="fr"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"Bonjour" in xliff_bytes

    def test_write_to_file(self):
        """XLIFF can be written to file."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test.xlf"
            gen.write_to_file(out_path)
            assert out_path.exists()
            assert out_path.stat().st_size > 0

    def test_write_to_file_creates_parent_dirs(self):
        """write_to_file creates parent directories."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "subdir" / "test.xlf"
            gen.write_to_file(out_path)
            assert out_path.exists()

    def test_read_back_validation(self):
        """Written file can be read back and validated."""
        from opp.xliff import XLIFFValidator
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test.xlf"
            gen.write_to_file(out_path)
            with open(out_path, "rb") as f:
                content = f.read()
            validator = XLIFFValidator()
            valid, errors = validator.validate_schema(content)
            assert valid is True

    def test_control_char_filtering(self):
        """Control characters are filtered."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello\x00World\x08Test", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, errors = validator.validate_schema(xliff_bytes)
        assert valid is True

    def test_xml_special_chars_in_output(self):
        """Special XML chars result in valid output."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Tom & Jerry <test> 'quote'", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, errors = validator.validate_schema(xliff_bytes)
        assert valid is True

    def test_unit_with_location(self):
        """Unit with location is added to XLIFF output."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en", location="doc.docx:42"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"Hello" in xliff_bytes

    def test_unit_with_resname_emits_attribute(self):
        """Phase B.1: resname attribute is set on the trans-unit.

        translate-toolkit has no setresname method, so the generator
        sets the attribute via xmlelement.set('resname', value).
        ORF consumes this in B.2 for position-based paragraph lookup.
        """
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(
            id="1", source="Hello", source_language="en",
            resname="para_index_42",
        ))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b'resname="para_index_42"' in xliff_bytes

    def test_unit_without_resname_omits_attribute(self):
        """Phase B.1: units without resname must not emit a resname attribute."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"resname" not in xliff_bytes

    def test_unit_with_context(self):
        """Unit with context note is added correctly."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en", context="Greeting text"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"Greeting text" in xliff_bytes

    def test_unit_with_state_approved(self):
        """Approved state is set correctly."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en", state=XLIFFUnitState.APPROVED))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, errors = validator.validate_schema(xliff_bytes)
        assert valid is True

    def test_multiple_units(self):
        """Multiple units are generated correctly."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        gen.add_unit(XLIFFTransUnit(id="2", source="World", source_language="en"))
        gen.add_unit(XLIFFTransUnit(id="3", source="Test", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        assert b"Hello" in xliff_bytes
        assert b"World" in xliff_bytes
        assert b"Test" in xliff_bytes

    def test_to_bytes_alias(self):
        """to_bytes returns same as generate_xliff_1_2."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        assert gen.to_bytes() == gen.generate_xliff_1_2()


class TestFromExtractionResultResnameContract:
    """ULTRAREADY-FIX (2026-06-08): every trans-unit emitted by
    `from_extraction_result` must carry a non-empty `resname` so that
    ORF's B.2 position-based backfill can find a target paragraph.
    The pre-fix code assigned `resname=None` for non-body content
    (table cells, header/footer paragraphs), which silently produced
    empty cells in the final DOCX because ORF's "No matching
    paragraph" fallback preserved the OPP source but the source XML
    was wiped by the backfill pass.
    """

    def _build_extraction_result(self):
        """Return an ExtractionResult with mixed body + non-body paragraphs.

        Body paragraph: para_index_in_body=0 (set by the body iterator).
        Non-body paragraphs: para_index_in_body=None (e.g. table cells,
        header/footer paragraphs) — these are the ones that previously
        ended up with resname=None and caused empty cells in the DOCX.
        """
        from opp.utils.dataclasses import (
            ExtractionResult, ParagraphData, TableData, ImageData, DocumentMetadata,
        )
        return ExtractionResult(
            paragraphs=[
                ParagraphData(text="Body paragraph", para_index_in_body=0),
                ParagraphData(text="Table cell A", para_index_in_body=None),
                ParagraphData(text="Table cell B", para_index_in_body=None),
            ],
            tables=[TableData(headers=[], rows=[])],
            images=[ImageData(data=b"", mime_type="image/png")],
            metadata=DocumentMetadata(),
        )

    def test_from_extraction_result_assigns_resname_to_every_unit(self):
        """RED: every trans-unit must have a non-empty resname."""
        result = self._build_extraction_result()
        gen = XLIFFFileGenerator.from_extraction_result(
            result, source_lang="zh", target_lang="en"
        )
        xliff_bytes = gen.generate_xliff_1_2()
        # Count resname= occurrences in the output.
        n_resname = xliff_bytes.count(b"resname=")
        n_trans_units = xliff_bytes.count(b"<trans-unit")
        assert n_trans_units == 3, f"expected 3 trans-units, got {n_trans_units}"
        assert n_resname == n_trans_units, (
            f"BUG: only {n_resname}/{n_trans_units} trans-units have resname; "
            f"the others will be silently dropped by ORF's backfill pass."
        )

    def test_from_extraction_result_resname_is_unique_per_unit(self):
        """Resname must be unique so ORF's position lookup can disambiguate."""
        result = self._build_extraction_result()
        gen = XLIFFFileGenerator.from_extraction_result(
            result, source_lang="zh", target_lang="en"
        )
        xliff_bytes = gen.generate_xliff_1_2()
        # Extract all resname values via simple regex.
        import re
        resnames = re.findall(rb'resname="([^"]+)"', xliff_bytes)
        assert len(resnames) == 3, f"expected 3 resnames, got {resnames!r}"
        assert len(set(resnames)) == 3, f"resnames are not unique: {resnames!r}"

    def test_from_extraction_result_body_para_keeps_para_index_prefix(self):
        """Body paragraphs should still use the `para_index_N` prefix (B.2 contract)."""
        result = self._build_extraction_result()
        gen = XLIFFFileGenerator.from_extraction_result(
            result, source_lang="zh", target_lang="en"
        )
        xliff_bytes = gen.generate_xliff_1_2()
        assert b'resname="para_index_0"' in xliff_bytes, (
            "the body paragraph should keep its para_index_0 resname "
            "(regression check on the B.2 contract)"
        )

    def test_from_extraction_result_non_body_para_gets_distinct_prefix(self):
        """Non-body paragraphs should get a distinct prefix (so ORF knows they're not body).

        The exact prefix is a contract between OPP and ORF. ORF's
        position-based backfill must be able to look up these units.
        """
        result = self._build_extraction_result()
        gen = XLIFFFileGenerator.from_extraction_result(
            result, source_lang="zh", target_lang="en"
        )
        xliff_bytes = gen.generate_xliff_1_2()
        # The 2 non-body paragraphs should have distinct resnames
        # with a non-`para_index_` prefix (so they're distinguishable).
        import re
        resnames = re.findall(rb'resname="([^"]+)"', xliff_bytes)
        non_body = [r for r in resnames if not r.startswith(b"para_index_")]
        assert len(non_body) == 2, (
            f"expected 2 non-body resnames with a distinct prefix, got {non_body!r}"
        )
        assert len(set(non_body)) == 2, f"non-body resnames not unique: {non_body!r}"