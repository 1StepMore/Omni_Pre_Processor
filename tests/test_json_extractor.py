import json
from pathlib import Path

import pytest

from opp.extractors.json import JSONExtractor


class TestJSONExtractor:
    """Test JSONExtractor following Phase 5 UTDD matrix."""

    @staticmethod
    def _parse_code_block(result):
        """Extract parsed JSON dict from the fenced code block paragraph."""
        assert len(result.paragraphs) == 1, \
            f"Expected 1 paragraph (fenced code block), got {len(result.paragraphs)}"
        text = result.paragraphs[0].text
        assert text.startswith("```json\n"), "Code block missing ```json opener"
        assert text.endswith("\n```"), "Code block missing closing ```"
        json_str = text[len("```json\n"):-len("\n```")]
        return json.loads(json_str)

    # ===== Normal Cases =====

    def test_json_produces_fenced_code_block(self, tmp_path: Path):
        """TDD: extraction must produce a fenced JSON code block, not flattened key=value pairs."""
        json_file = tmp_path / "flat.json"
        json_file.write_text('{"name": "test", "value": 123}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] == "test"
        assert data["value"] == 123

    def test_extract_flat_object(self, tmp_path: Path):
        """Normal: Extract flat JSON object."""
        json_file = tmp_path / "flat.json"
        json_file.write_text('{"name": "test", "value": "123"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] == "test"
        assert data["value"] == "123"

    def test_extract_nested_dot_notation(self, tmp_path: Path):
        """Normal: Extract nested JSON preserved as structured code block."""
        json_file = tmp_path / "nested.json"
        json_file.write_text(
            '{"user": {"name": "Alice", "age": 30}, "active": true}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["user"]["name"] == "Alice"
        assert data["user"]["age"] == 30
        assert data["active"] is True

    def test_extract_array_indexing(self, tmp_path: Path):
        """Normal: Extract JSON array preserved as structured code block."""
        json_file = tmp_path / "array.json"
        json_file.write_text(
            '{"items": ["first", "second", "third"]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["items"] == ["first", "second", "third"]

    def test_extract_deeply_nested_depth_5(self, tmp_path: Path):
        """Normal: Extract nested depth 5 preserved in code block."""
        json_file = tmp_path / "depth5.json"
        json_file.write_text(
            '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'  ,
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["a"]["b"]["c"]["d"]["e"] == "deep"

    def test_extract_mixed_types(self, tmp_path: Path):
        """Normal: Extract JSON with mixed value types preserved."""
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            '{"str": "text", "int": 42, "float": 3.14, "bool": false, "null": null}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["str"] == "text"
        assert data["int"] == 42
        assert data["float"] == 3.14
        assert data["bool"] is False
        assert data["null"] is None

    def test_extract_root_array(self, tmp_path: Path):
        """Normal: Extract JSON with root-level array preserved."""
        json_file = tmp_path / "root_array.json"
        json_file.write_text('["one", "two", "three"]', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data == ["one", "two", "three"]

    def test_extract_empty_string_skipped(self, tmp_path: Path):
        """Normal: Empty strings preserved in fenced code block."""
        json_file = tmp_path / "empty_str.json"
        json_file.write_text('{"name": "", "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] == ""
        assert data["value"] == "valid"

    # ===== Boundary Cases =====

    def test_extract_depth_8_boundary(self, tmp_path: Path):
        """Boundary: Deep nesting preserved in fenced code block."""
        json_file = tmp_path / "depth8.json"
        json_file.write_text(
            '{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":"depth8"}}}}}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["a"]["b"]["c"]["d"]["e"]["f"]["g"]["h"] == "depth8"

    def test_extract_depth_10_exceeds_limit(self, tmp_path: Path):
        """Boundary: Deep nesting preserved as-is in code block (no flattening truncation)."""
        json_file = tmp_path / "depth10.json"
        json_file.write_text(
            '{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":{"i":{"j":"exceeds"}}}}}}}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["a"]["b"]["c"]["d"]["e"]["f"]["g"]["h"]["i"]["j"] == "exceeds"

    def test_extract_large_array(self, tmp_path: Path):
        """Boundary: Large array preserved in single fenced code block."""
        json_file = tmp_path / "large_array.json"
        data = {"items": list(range(1000))}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        parsed = self._parse_code_block(result)

        assert len(parsed["items"]) == 1000

    def test_extract_wide_nested(self, tmp_path: Path):
        """Boundary: Many siblings preserved in single code block."""
        json_file = tmp_path / "wide.json"
        data = {"level1": {f"key{i}": f"value{i}" for i in range(100)}}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        parsed = self._parse_code_block(result)

        assert len(parsed["level1"]) == 100

    def test_extract_empty_object(self, tmp_path: Path):
        """Boundary: Empty JSON object in fenced code block."""
        json_file = tmp_path / "empty_obj.json"
        json_file.write_text('{}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 1
        assert "{}" in result.paragraphs[0].text

    def test_extract_empty_array(self, tmp_path: Path):
        """Boundary: Empty JSON array in fenced code block."""
        json_file = tmp_path / "empty_arr.json"
        json_file.write_text('[]', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 1
        assert "[]" in result.paragraphs[0].text

    # ===== Exception Cases =====

    def test_extract_invalid_json(self, tmp_path: Path):
        """Exception: Invalid JSON should raise JSONDecodeError."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text('{not valid json}', encoding="utf-8")

        extractor = JSONExtractor()
        with pytest.raises(json.JSONDecodeError):
            extractor.extract(json_file)

    def test_extract_truncated_json(self, tmp_path: Path):
        """Exception: Truncated JSON should raise error."""
        json_file = tmp_path / "truncated.json"
        json_file.write_text('{"incomplete": ', encoding="utf-8")

        extractor = JSONExtractor()
        with pytest.raises(json.JSONDecodeError):
            extractor.extract(json_file)

    def test_extract_bom_json(self, tmp_path: Path):
        """Exception: JSON with BOM should be handled correctly."""
        json_file = tmp_path / "bom.json"
        content = '{"name": "bom_test", "value": 123}'
        json_file.write_bytes(b'\xef\xbb\xbf' + content.encode('utf-8'))

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] == "bom_test"
        assert data["value"] == 123

    def test_extract_duplicate_keys(self, tmp_path: Path):
        """Exception: JSON with duplicate keys - later value should win."""
        json_file = tmp_path / "duplicates.json"
        json_file.write_text('{"name": "first", "name": "second"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] == "second"

    def test_extract_none_value_skipped(self, tmp_path: Path):
        """Exception: Null values are preserved in fenced code block."""
        json_file = tmp_path / "none_val.json"
        json_file.write_text('{"name": null, "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["name"] is None
        assert data["value"] == "valid"

    def test_extract_unicode_content(self, tmp_path: Path):
        """Exception: JSON with Unicode characters preserved."""
        json_file = tmp_path / "unicode.json"
        json_file.write_text(
            '{"chinese": "中文测试", "emoji": "😀🎉", "japanese": "日本語"}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["chinese"] == "中文测试"
        assert data["emoji"] == "😀🎉"
        assert data["japanese"] == "日本語"

    def test_extract_special_chars_in_strings(self, tmp_path: Path):
        """Exception: JSON strings with special characters preserved."""
        json_file = tmp_path / "special.json"
        json_file.write_text(
            '{"newlines": "line1\\nline2", "tabs": "col1\\tcol2", "quotes": "say \\"hi\\""}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert "line1" in data["newlines"]
        assert "line2" in data["newlines"]
        assert "\t" in data["tabs"] or "col1" in data["tabs"]

    def test_extract_number_types(self, tmp_path: Path):
        """Exception: JSON numbers preserved with correct types."""
        json_file = tmp_path / "numbers.json"
        json_file.write_text(
            '{"int": 42, "float": 3.14159, "scientific": 1.23e10, "negative": -17}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["int"] == 42
        assert data["float"] == 3.14159
        assert data["negative"] == -17

    def test_extract_boolean_values(self, tmp_path: Path):
        """Exception: JSON boolean values preserved."""
        json_file = tmp_path / "booleans.json"
        json_file.write_text('{"true_val": true, "false_val": false}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["true_val"] is True
        assert data["false_val"] is False

    def test_extract_whitespace_only(self, tmp_path: Path):
        """Exception: JSON file with only whitespace."""
        json_file = tmp_path / "whitespace.json"
        json_file.write_text('   \n\t  \n  ', encoding="utf-8")

        extractor = JSONExtractor()
        with pytest.raises(json.JSONDecodeError):
            extractor.extract(json_file)

    def test_extract_nested_array_mixing(self, tmp_path: Path):
        """Exception: JSON with nested arrays and objects preserved."""
        json_file = tmp_path / "mixed_nested.json"
        json_file.write_text(
            '{"data": [{"name": "a", "items": [1, 2]}, {"name": "b", "items": [3, 4]}]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block(result)

        assert data["data"][0]["name"] == "a"
        assert data["data"][0]["items"] == [1, 2]
        assert data["data"][1]["name"] == "b"
        assert data["data"][1]["items"] == [3, 4]

    def test_supported_extensions(self):
        """Verify supported file extensions."""
        extractor = JSONExtractor()
        assert ".json" in extractor.supported_extensions()

class TestJSONExtractorKeyValues:
    """Test JSONExtractor.extract_key_values() method - Phase 5."""

    def test_extract_key_values_nested_objects(self, tmp_path: Path):
        """Nested objects are flattened with dot notation."""
        json_file = tmp_path / "nested.json"
        json_file.write_text(
            '{"user": {"name": "Alice", "address": {"city": "Beijing"}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert result["user.name"] == "Alice"
        assert result["user.address.city"] == "Beijing"
        assert len(result) == 2

    def test_extract_key_values_arrays(self, tmp_path: Path):
        """Array elements use numeric indices."""
        json_file = tmp_path / "arrays.json"
        json_file.write_text(
            '{"items": ["first", "second", "third"]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert result["items.0"] == "first"
        assert result["items.1"] == "second"
        assert result["items.2"] == "third"

    def test_extract_key_values_mixed_types(self, tmp_path: Path):
        """Mixed value types are preserved."""
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            '{"str": "text", "int": 42, "float": 3.14, "bool": true}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert result["str"] == "text"
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["bool"] == True

    def test_extract_key_values_empty_string_skipped(self, tmp_path: Path):
        """Empty string values are skipped."""
        json_file = tmp_path / "empty_str.json"
        json_file.write_text('{"name": "", "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert "name" not in result
        assert result["value"] == "valid"

    def test_extract_key_values_null_skipped(self, tmp_path: Path):
        """Null values are skipped."""
        json_file = tmp_path / "nulls.json"
        json_file.write_text('{"name": null, "value": "valid", "empty": null}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert "name" not in result
        assert "empty" not in result
        assert result["value"] == "valid"
        assert len(result) == 1

    def test_extract_key_values_deep_nesting(self, tmp_path: Path):
        """Deeply nested structures are flattened."""
        json_file = tmp_path / "deep.json"
        json_file.write_text(
            '{"a": {"b": {"c": {"d": "deep"}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract_key_values(json_file)

        assert result["a.b.c.d"] == "deep"
