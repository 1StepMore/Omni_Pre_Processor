"""Tests for KeyValueChannel."""

import pytest

from opp.channels.keyvalue_channel import KeyValueChannel


class TestKeyValueChannel:
    """Test suite for KeyValueChannel."""

    def test_simple_dict(self):
        """Simple key-value dict is converted to XLIFF."""
        channel = KeyValueChannel()
        data = {"greeting": "Hello", "farewell": "Goodbye"}
        result = channel.convert(data)

        assert isinstance(result, str)
        assert "greeting" in result
        assert "Hello" in result
        assert "farewell" in result
        assert "Goodbye" in result

    def test_nested_keys(self):
        """Dot-notation keys are preserved in context notes."""
        channel = KeyValueChannel()
        data = {"ui.menu.save": "Save", "ui.menu.exit": "Exit", "dialog.cancel": "Cancel"}
        result = channel.convert(data)

        assert "ui.menu.save" in result
        assert "Context: ui.menu.save" in result
        assert "ui.menu.exit" in result
        assert "dialog.cancel" in result

    def test_empty_dict(self):
        """Empty dict returns valid empty XLIFF."""
        channel = KeyValueChannel()
        result = channel.convert({})

        assert isinstance(result, str)
        assert "<xliff" in result
        assert "</xliff>" in result

    def test_many_keys(self):
        """Dict with 100+ keys is handled correctly."""
        channel = KeyValueChannel()
        data = {f"key.{i}": f"Value {i}" for i in range(150)}
        result = channel.convert(data)

        assert isinstance(result, str)
        for i in range(150):
            assert f"key.{i}" in result
            assert f"Value {i}" in result

    def test_null_value_skip(self):
        """Null values are skipped by default."""
        channel = KeyValueChannel()
        data = {"valid": "Hello", "null_val": None, "another": "World"}
        result = channel.convert(data)

        assert "Hello" in result
        assert "World" in result
        assert "null_val" not in result

    def test_empty_string_skip(self):
        """Empty string values are skipped by default."""
        channel = KeyValueChannel()
        data = {"valid": "Hello", "empty_val": "", "another": "World"}
        result = channel.convert(data)

        assert "Hello" in result
        assert "World" in result
        assert "empty_val" not in result

    def test_null_values_included_when_not_skipping(self):
        """Null values are included when skip_empty=False."""
        channel = KeyValueChannel(skip_empty=False)
        data = {"valid": "Hello", "null_val": None}
        result = channel.convert(data)

        assert "Hello" in result
        assert "null_val" in result

    def test_empty_string_included_when_not_skipping(self):
        """Empty string values are included when skip_empty=False."""
        channel = KeyValueChannel(skip_empty=False)
        data = {"valid": "Hello", "empty_val": ""}
        result = channel.convert(data)

        assert "Hello" in result
        assert "empty_val" in result

    def test_non_dict_input_raises(self):
        """Non-dict input raises ValueError."""
        channel = KeyValueChannel()
        with pytest.raises(ValueError, match="data cannot be None"):
            channel.convert(None)

    def test_convert_to_file(self):
        """convert_to_file returns bytes and optionally writes to path."""
        channel = KeyValueChannel()
        data = {"key1": "Value1"}
        result = channel.convert_to_file(data)

        assert isinstance(result, bytes)
        assert b"key1" in result
        assert b"Value1" in result

    def test_trans_unit_ids_unique(self):
        """Each key becomes a unique trans-unit id."""
        channel = KeyValueChannel()
        data = {"key1": "Value1", "key2": "Value2", "key3": "Value3"}
        result = channel.convert(data)

        assert result.count('id="key1"') == 1
        assert result.count('id="key2"') == 1
        assert result.count('id="key3"') == 1