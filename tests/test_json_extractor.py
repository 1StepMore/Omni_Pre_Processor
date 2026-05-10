import json
from pathlib import Path

import pytest

from opp.extractors.json import JSONExtractor


class TestJSONExtractor:
    """Test JSONExtractor following Phase 5 UTDD matrix."""

    # ===== Normal Cases =====

    def test_extract_flat_object(self, tmp_path: Path):
        """Normal: Extract flat JSON object."""
        json_file = tmp_path / "flat.json"
        json_file.write_text('{"name": "test", "value": "123"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 2
        texts = [p.text for p in result.paragraphs]
        assert any("name = test" in t for t in texts)
        assert any("value = 123" in t for t in texts)

    def test_extract_nested_dot_notation(self, tmp_path: Path):
        """Normal: Extract nested JSON with dot notation."""
        json_file = tmp_path / "nested.json"
        json_file.write_text(
            '{"user": {"name": "Alice", "age": 30}, "active": true}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("user.name = Alice" in t for t in texts)
        assert any("user.age = 30" in t for t in texts)
        assert any("active = True" in t for t in texts)

    def test_extract_array_indexing(self, tmp_path: Path):
        """Normal: Extract JSON array with numeric indexing."""
        json_file = tmp_path / "array.json"
        json_file.write_text(
            '{"items": ["first", "second", "third"]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("items.0 = first" in t for t in texts)
        assert any("items.1 = second" in t for t in texts)
        assert any("items.2 = third" in t for t in texts)

    def test_extract_deeply_nested_depth_5(self, tmp_path: Path):
        """Normal: Extract nested depth 5 (within MAX_DEPTH=8)."""
        json_file = tmp_path / "depth5.json"
        json_file.write_text(
            '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'  ,
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("a.b.c.d.e = deep" in t for t in texts)

    def test_extract_mixed_types(self, tmp_path: Path):
        """Normal: Extract JSON with mixed value types."""
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            '{"str": "text", "int": 42, "float": 3.14, "bool": false, "null": null}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        # null values are filtered out
        texts = [p.text for p in result.paragraphs]
        assert any('str = text' in t for t in texts)
        assert any('int = 42' in t for t in texts)
        assert any('float = 3.14' in t for t in texts)
        assert any('bool = False' in t for t in texts)
        # null values should not appear
        assert not any('null' in t for t in texts)

    def test_extract_root_array(self, tmp_path: Path):
        """Normal: Extract JSON with root-level array."""
        json_file = tmp_path / "root_array.json"
        json_file.write_text('["one", "two", "three"]', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("root.0 = one" in t for t in texts)
        assert any("root.1 = two" in t for t in texts)
        assert any("root.2 = three" in t for t in texts)

    def test_extract_empty_string_skipped(self, tmp_path: Path):
        """Normal: Empty string values are skipped."""
        json_file = tmp_path / "empty_str.json"
        json_file.write_text('{"name": "", "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        # Empty string key should not appear
        assert len([t for t in texts if "name =" in t]) == 0
        assert any("value = valid" in t for t in texts)

    # ===== Boundary Cases =====

    def test_extract_depth_8_boundary(self, tmp_path: Path):
        """Boundary: Extract at exactly MAX_DEPTH=8."""
        json_file = tmp_path / "depth8.json"
        # Create nesting that reaches depth 8
        json_file.write_text(
            '{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":"depth8"}}}}}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        # Should NOT be truncated at depth 8
        assert any("a.b.c.d.e.f.g.h = depth8" in t for t in texts)

    def test_extract_depth_10_exceeds_limit(self, tmp_path: Path):
        """Boundary: Extract at depth 10 (exceeds MAX_DEPTH=8) - should truncate."""
        json_file = tmp_path / "depth10.json"
        # Create nesting that exceeds MAX_DEPTH
        json_file.write_text(
            '{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":{"i":{"j":"exceeds"}}}}}}}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        # Should have warning about exceeding depth
        assert len(result.warnings) > 0
        assert any("最大嵌套深度" in w or "depth" in w.lower() for w in result.warnings)

    def test_extract_large_array(self, tmp_path: Path):
        """Boundary: Extract JSON with large array (1000 elements)."""
        json_file = tmp_path / "large_array.json"
        data = {"items": list(range(1000))}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        # Should extract 1000 items
        assert len(result.paragraphs) == 1000
        texts = [p.text for p in result.paragraphs]
        assert any("items.0 = 0" in t for t in texts)
        assert any("items.999 = 999" in t for t in texts)

    def test_extract_wide_nested(self, tmp_path: Path):
        """Boundary: Extract JSON with many siblings at same level."""
        json_file = tmp_path / "wide.json"
        data = {"level1": {f"key{i}": f"value{i}" for i in range(100)}}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 100

    def test_extract_empty_object(self, tmp_path: Path):
        """Boundary: Extract empty JSON object."""
        json_file = tmp_path / "empty_obj.json"
        json_file.write_text('{}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 0

    def test_extract_empty_array(self, tmp_path: Path):
        """Boundary: Extract empty JSON array."""
        json_file = tmp_path / "empty_arr.json"
        json_file.write_text('[]', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 0

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
        # UTF-8 BOM (0xEF 0xBB 0xBF)
        content = '\ufeff{"name": "bom_test", "value": 123}'
        json_file.write_bytes(content.encode('utf-8-sig'))

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        # BOM should not appear in output
        texts = [p.text for p in result.paragraphs]
        assert not any('\ufeff' in t for t in texts)
        assert any("name = bom_test" in t for t in texts)

    def test_extract_duplicate_keys(self, tmp_path: Path):
        """Exception: JSON with duplicate keys - later value should win."""
        json_file = tmp_path / "duplicates.json"
        json_file.write_text('{"name": "first", "name": "second"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        # Python's json.load keeps last value for duplicates
        texts = [p.text for p in result.paragraphs]
        assert any("name = second" in t for t in texts)
        # Should not have duplicate entries with different values
        name_texts = [t for t in texts if "name = " in t]
        assert len(name_texts) == 1

    def test_extract_none_value_skipped(self, tmp_path: Path):
        """Exception: None values should be skipped."""
        json_file = tmp_path / "none_val.json"
        json_file.write_text('{"name": null, "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        # None values should not appear
        assert not any("name" in t and "null" in t for t in texts)
        assert any("value = valid" in t for t in texts)

    def test_extract_unicode_content(self, tmp_path: Path):
        """Exception: JSON with Unicode characters."""
        json_file = tmp_path / "unicode.json"
        json_file.write_text(
            '{"chinese": "中文测试", "emoji": "😀🎉", "japanese": "日本語"}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("chinese = 中文测试" in t for t in texts)
        assert any("emoji = 😀🎉" in t for t in texts)
        assert any("japanese = 日本語" in t for t in texts)

    def test_extract_special_chars_in_strings(self, tmp_path: Path):
        """Exception: JSON strings with special characters."""
        json_file = tmp_path / "special.json"
        json_file.write_text(
            '{"newlines": "line1\\nline2", "tabs": "col1\\tcol2", "quotes": "say \\"hi\\""}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("newlines = line1" in t and "line2" in t for t in texts)

    def test_extract_number_types(self, tmp_path: Path):
        """Exception: JSON numbers (int, float, scientific notation)."""
        json_file = tmp_path / "numbers.json"
        json_file.write_text(
            '{"int": 42, "float": 3.14159, "scientific": 1.23e10, "negative": -17}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("int = 42" in t for t in texts)
        assert any("float = 3.14159" in t for t in texts)
        assert any("scientific = 1.23e+10" in t or "scientific = 12300000000.0" in t for t in texts)
        assert any("negative = -17" in t for t in texts)

    def test_extract_boolean_values(self, tmp_path: Path):
        """Exception: JSON boolean values."""
        json_file = tmp_path / "booleans.json"
        json_file.write_text('{"true_val": true, "false_val": false}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("true_val = True" in t for t in texts)
        assert any("false_val = False" in t for t in texts)

    def test_extract_whitespace_only(self, tmp_path: Path):
        """Exception: JSON file with only whitespace."""
        json_file = tmp_path / "whitespace.json"
        json_file.write_text('   \n\t  \n  ', encoding="utf-8")

        extractor = JSONExtractor()
        with pytest.raises(json.JSONDecodeError):
            extractor.extract(json_file)

    def test_extract_nested_array_mixing(self, tmp_path: Path):
        """Exception: JSON with nested arrays and objects mixed."""
        json_file = tmp_path / "mixed_nested.json"
        json_file.write_text(
            '{"data": [{"name": "a", "items": [1, 2]}, {"name": "b", "items": [3, 4]}]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        texts = [p.text for p in result.paragraphs]
        assert any("data.0.name = a" in t for t in texts)
        assert any("data.0.items.0 = 1" in t for t in texts)
        assert any("data.1.name = b" in t for t in texts)
        assert any("data.1.items.1 = 4" in t for t in texts)

    def test_supported_extensions(self):
        """Verify supported file extensions."""
        extractor = JSONExtractor()
        assert ".json" in extractor.supported_extensions()