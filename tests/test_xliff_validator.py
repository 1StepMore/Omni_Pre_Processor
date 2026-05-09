"""Tests for XLIFFValidator."""

import pytest
from pathlib import Path
import tempfile

from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit, XLIFFValidator


class TestXLIFFValidator:
    """Test suite for XLIFFValidator."""

    def test_validator_creation(self):
        """XLIFFValidator can be created."""
        validator = XLIFFValidator()
        assert validator is not None

    def test_validate_valid_xliff(self):
        """Valid XLIFF passes schema validation."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, errors = validator.validate_schema(xliff_bytes)
        assert valid is True
        assert len(errors) == 0

    def test_validate_malformed_xml(self):
        """Malformed XML fails validation."""
        validator = XLIFFValidator()
        valid, errors = validator.validate_schema(b"<xliff><unclosed>")
        assert valid is False
        assert len(errors) > 0

    def test_validate_trans_units_valid(self):
        """Valid trans-units pass unit validation."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        gen.add_unit(XLIFFTransUnit(id="2", source="World", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is True
        assert len(errors) == 0

    def test_validate_trans_units_empty_source(self):
        """Empty source generates error."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is False
        assert any("source" in e.lower() and "empty" in e.lower() for e in errors)

    def test_validate_trans_units_duplicate_ids(self):
        """Duplicate IDs generate error."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="First", source_language="en"))
        gen.add_unit(XLIFFTransUnit(id="1", source="Second", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is False
        assert any("duplicate" in e.lower() or "1" in e for e in errors)

    def test_validate_trans_units_missing_target(self):
        """Missing target generates warning."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", source_language="en"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is True
        assert any("target" in w.lower() for w in warnings)

    def test_validate_trans_units_with_target(self):
        """Unit with target passes without warning."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Hello", target="Bonjour", source_language="en", target_language="fr"))
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is True
        target_warnings = [w for w in warnings if "target" in w.lower()]
        assert len(target_warnings) == 0

    def test_validate_trans_units_no_units(self):
        """No trans-units generates warning."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="fr")
        gen = XLIFFFileGenerator(attributes=attrs)
        xliff_bytes = gen.generate_xliff_1_2()
        validator = XLIFFValidator()
        valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
        assert valid is True
        assert any("no trans-unit" in w.lower() for w in warnings)

    def test_roundtrip_write_read(self):
        """Write, read, and validate produces consistent results."""
        attrs = XLIFFFileAttributes(source_language="en", target_language="de")
        gen = XLIFFFileGenerator(attributes=attrs)
        gen.add_unit(XLIFFTransUnit(id="1", source="Introduction", source_language="en"))
        gen.add_unit(XLIFFTransUnit(id="2", source="Chapter 1", source_language="en"))
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test.xlf"
            gen.write_to_file(out_path)
            with open(out_path, "rb") as f:
                content = f.read()
        validator = XLIFFValidator()
        schema_valid, schema_errors = validator.validate_schema(content)
        units_valid, units_warnings, units_errors = validator.validate_trans_units(content)
        assert schema_valid is True
        assert units_valid is True