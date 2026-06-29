import json
from pathlib import Path

import pytest

from opp.extractors.json import JSONExtractor


class TestJSONExtractor:
    """Test JSONExtractor — now emits fenced block + json_field: kv lines."""

    @staticmethod
    def _parse_code_block(result):
        """Extract (parsed JSON dict, translations dict) from extraction result.

        The new extract() format emits:
          para[0] = ```json fenced code block (full original JSON)
          para[1..] = json_field:path = value lines (one per string leaf)
        """
        assert len(result.paragraphs) >= 1, \
            f"Expected at least 1 paragraph (fenced code block), got {len(result.paragraphs)}"
        text = result.paragraphs[0].text
        assert text.startswith("```json\n"), "Code block missing ```json opener"
        assert text.endswith("\n```"), "Code block missing closing ```"
        json_str = text[len("```json\n"):-len("\n```")]
        data = json.loads(json_str)

        # Build translations dict from kv paragraphs
        translations: dict[str, str] = {}
        for p in result.paragraphs[1:]:
            if p.text.startswith("json_field:"):
                _, rest = p.text.split("json_field:", 1)
                path, _, value = rest.partition(" = ")
                translations[path] = value

        return data, translations

    @staticmethod
    def _parse_code_block_legacy(result):
        """Legacy helper: return just the parsed data (for tests that don't need translations)."""
        data, _ = TestJSONExtractor._parse_code_block(result)
        return data

    # ===== Normal Cases =====

    def test_json_produces_fenced_code_block(self, tmp_path: Path):
        """TDD: extraction produces a fenced JSON code block + json_field: kv lines."""
        json_file = tmp_path / "flat.json"
        json_file.write_text('{"name": "test", "value": 123}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["name"] == "test"
        assert data["value"] == 123
        # Only string values get kv lines
        assert "name" in translations
        assert translations["name"] == "test"

    def test_extract_flat_object(self, tmp_path: Path):
        """Normal: Extract flat JSON object — fenced block + kv lines for all strings."""
        json_file = tmp_path / "flat.json"
        json_file.write_text('{"name": "test", "value": "123"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

        assert data["name"] == "test"
        assert data["value"] == "123"

    def test_extract_nested_dot_notation(self, tmp_path: Path):
        """Normal: Extract nested JSON — fenced block preserves structure."""
        json_file = tmp_path / "nested.json"
        json_file.write_text(
            '{"user": {"name": "Alice", "age": 30}, "active": true}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["user"]["name"] == "Alice"
        assert data["user"]["age"] == 30
        assert data["active"] is True
        # Only "Alice" is a string → one kv line
        assert translations == {"user.name": "Alice"}

    def test_extract_array_indexing(self, tmp_path: Path):
        """Normal: Extract JSON array — fenced block preserves structure."""
        json_file = tmp_path / "array.json"
        json_file.write_text(
            '{"items": ["first", "second", "third"]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

        assert data["items"] == ["first", "second", "third"]

    def test_extract_deeply_nested_depth_5(self, tmp_path: Path):
        """Normal: Extract nested depth 5 preserved in code block."""
        json_file = tmp_path / "depth5.json"
        json_file.write_text(
            '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

        assert data["a"]["b"]["c"]["d"]["e"] == "deep"

    def test_extract_mixed_types(self, tmp_path: Path):
        """Normal: Extract JSON with mixed value types — non-strings preserved in fence only."""
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            '{"str": "text", "int": 42, "float": 3.14, "bool": false, "null": null}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["str"] == "text"
        assert data["int"] == 42
        assert data["float"] == 3.14
        assert data["bool"] is False
        assert data["null"] is None
        # Only "str" is a string → one kv line
        assert set(translations.keys()) == {"str"}
        assert translations["str"] == "text"

    def test_extract_root_array(self, tmp_path: Path):
        """Normal: Extract JSON with root-level array — fenced block preserves structure."""
        json_file = tmp_path / "root_array.json"
        json_file.write_text('["one", "two", "three"]', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

        assert data == ["one", "two", "three"]

    def test_extract_empty_string_skipped(self, tmp_path: Path):
        """Normal: Empty strings preserved in fenced code block, skipped in kv lines."""
        json_file = tmp_path / "empty_str.json"
        json_file.write_text('{"name": "", "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["name"] == ""
        assert data["value"] == "valid"
        # Empty string "name" is skipped; only "value" has a kv line
        assert set(translations.keys()) == {"value"}
        assert translations["value"] == "valid"

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
        data = self._parse_code_block_legacy(result)

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
        data = self._parse_code_block_legacy(result)

        assert data["a"]["b"]["c"]["d"]["e"]["f"]["g"]["h"]["i"]["j"] == "exceeds"

    def test_extract_large_array(self, tmp_path: Path):
        """Boundary: Large array preserved in single fenced code block."""
        json_file = tmp_path / "large_array.json"
        data = {"items": list(range(1000))}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        parsed = self._parse_code_block_legacy(result)

        assert len(parsed["items"]) == 1000

    def test_extract_wide_nested(self, tmp_path: Path):
        """Boundary: Many siblings preserved in single code block."""
        json_file = tmp_path / "wide.json"
        data = {"level1": {f"key{i}": f"value{i}" for i in range(100)}}
        json_file.write_text(json.dumps(data), encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        parsed = self._parse_code_block_legacy(result)

        assert len(parsed["level1"]) == 100

    def test_extract_empty_object(self, tmp_path: Path):
        """Boundary: Empty JSON object — only fenced block, no kv lines."""
        json_file = tmp_path / "empty_obj.json"
        json_file.write_text('{}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)

        assert len(result.paragraphs) == 1
        assert "{}" in result.paragraphs[0].text

    def test_extract_empty_array(self, tmp_path: Path):
        """Boundary: Empty JSON array — only fenced block, no kv lines."""
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
        data = self._parse_code_block_legacy(result)

        assert data["name"] == "bom_test"
        assert data["value"] == 123

    def test_extract_duplicate_keys(self, tmp_path: Path):
        """Exception: JSON with duplicate keys - later value should win."""
        json_file = tmp_path / "duplicates.json"
        json_file.write_text('{"name": "first", "name": "second"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

        assert data["name"] == "second"

    def test_extract_none_value_skipped(self, tmp_path: Path):
        """Exception: Null values are preserved in fenced code block, skipped in kv."""
        json_file = tmp_path / "none_val.json"
        json_file.write_text('{"name": null, "value": "valid"}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["name"] is None
        assert data["value"] == "valid"
        # null skipped; only "value" has a kv line
        assert set(translations.keys()) == {"value"}
        assert translations["value"] == "valid"

    def test_extract_unicode_content(self, tmp_path: Path):
        """Exception: JSON with Unicode characters preserved."""
        json_file = tmp_path / "unicode.json"
        json_file.write_text(
            '{"chinese": "中文测试", "emoji": "😀🎉", "japanese": "日本語"}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

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
        data = self._parse_code_block_legacy(result)

        assert "line1" in data["newlines"]
        assert "line2" in data["newlines"]
        assert "\t" in data["tabs"] or "col1" in data["tabs"]

    def test_extract_number_types(self, tmp_path: Path):
        """Exception: JSON numbers preserved with correct types — no kv lines emitted."""
        json_file = tmp_path / "numbers.json"
        json_file.write_text(
            '{"int": 42, "float": 3.14159, "scientific": 1.23e10, "negative": -17}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["int"] == 42
        assert data["float"] == 3.14159
        assert data["negative"] == -17
        # No strings → no kv lines beyond the fence
        assert translations == {}

    def test_extract_boolean_values(self, tmp_path: Path):
        """Exception: JSON boolean values preserved — no kv lines emitted."""
        json_file = tmp_path / "booleans.json"
        json_file.write_text('{"true_val": true, "false_val": false}', encoding="utf-8")

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data, translations = self._parse_code_block(result)

        assert data["true_val"] is True
        assert data["false_val"] is False
        assert translations == {}

    def test_extract_whitespace_only(self, tmp_path: Path):
        """Exception: JSON file with only whitespace."""
        json_file = tmp_path / "whitespace.json"
        json_file.write_text('   \n\t  \n  ', encoding="utf-8")

        extractor = JSONExtractor()
        with pytest.raises(json.JSONDecodeError):
            extractor.extract(json_file)

    def test_extract_nested_array_mixing(self, tmp_path: Path):
        """Exception: JSON with nested arrays and objects — fence preserves structure."""
        json_file = tmp_path / "mixed_nested.json"
        json_file.write_text(
            '{"data": [{"name": "a", "items": [1, 2]}, {"name": "b", "items": [3, 4]}]}',
            encoding="utf-8"
        )

        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        data = self._parse_code_block_legacy(result)

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


class TestJSONExtractorTranslations:
    """Verify json_field: kv line emission for translatable strings."""

    def test_simple_object_has_kv_lines(self, tmp_path: Path):
        json_file = tmp_path / "simple.json"
        json_file.write_text('{"name": "Alice"}', encoding="utf-8")
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # 1 fence + 1 kv line
        assert len(result.paragraphs) == 2
        assert result.paragraphs[0].text.startswith("```json")
        assert result.paragraphs[1].text == "json_field:name = Alice"

    def test_nested_object_kv_paths(self, tmp_path: Path):
        json_file = tmp_path / "nested.json"
        json_file.write_text('{"user": {"name": "Alice", "age": 30}}', encoding="utf-8")
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # 1 fence + 1 kv (only "Alice" is string; 30 is number, no kv)
        assert len(result.paragraphs) == 2
        assert result.paragraphs[1].text == "json_field:user.name = Alice"

    def test_array_elements_kv_paths(self, tmp_path: Path):
        json_file = tmp_path / "array.json"
        json_file.write_text('["a", "b", "c"]', encoding="utf-8")
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # 1 fence + 3 kv lines (indices .0 .1 .2)
        assert len(result.paragraphs) == 4
        assert result.paragraphs[1].text == "json_field:0 = a"
        assert result.paragraphs[2].text == "json_field:1 = b"
        assert result.paragraphs[3].text == "json_field:2 = c"

    def test_non_strings_no_kv(self, tmp_path: Path):
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            '{"name": "Alice", "age": 30, "active": true, "data": null}',
            encoding="utf-8"
        )
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # 1 fence + 1 kv (only "name" is a string)
        assert len(result.paragraphs) == 2
        assert result.paragraphs[1].text == "json_field:name = Alice"

    def test_empty_string_no_kv(self, tmp_path: Path):
        json_file = tmp_path / "empties.json"
        json_file.write_text('{"a": "", "b": "valid"}', encoding="utf-8")
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # 1 fence + 1 kv (only "b" is non-empty string)
        assert len(result.paragraphs) == 2
        assert result.paragraphs[1].text == "json_field:b = valid"

    def test_unicode_in_kv_values(self, tmp_path: Path):
        json_file = tmp_path / "unicode.json"
        json_file.write_text(
            '{"chinese": "中文测试", "japanese": "日本語テスト"}',
            encoding="utf-8"
        )
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        assert len(result.paragraphs) == 3  # 1 fence + 2 kv
        kv_texts = {p.text for p in result.paragraphs[1:]}
        assert "json_field:chinese = 中文测试" in kv_texts
        assert "json_field:japanese = 日本語テスト" in kv_texts

    def test_max_depth_warns_but_continues(self, tmp_path: Path):
        """Depth > 8: _walk_strings doesn't truncate, so deep strings still get kv lines."""
        deep = {}
        cur = deep
        for i in range(10):
            cur["n"] = {}
            cur = cur["n"]
        cur["leaf"] = "deep_value"
        json_file = tmp_path / "deep.json"
        json_file.write_text(json.dumps(deep), encoding="utf-8")
        extractor = JSONExtractor()
        result = extractor.extract(json_file)
        # Fence + 1 kv for the leaf (walk_strings has no depth limit)
        assert len(result.paragraphs) >= 2
        kv_texts = [p.text for p in result.paragraphs[1:]]
        assert any("deep_value" in t for t in kv_texts)


class TestJSONExtractorRoundTrip:
    """End-to-end round-trip: JSON → extract → mock-translate → verify structure."""

    @staticmethod
    def _mock_translate(paras):
        """Simulate OL translation by appending [TR] to each kv value."""
        from opp.utils.dataclasses import ParagraphData
        out = []
        for p in paras:
            if p.text.startswith("json_field:"):
                prefix, _, value = p.text.partition(" = ")
                out.append(ParagraphData(text=f"{prefix} = {value} [TR]"))
            else:
                out.append(p)
        return out

    def _round_trip(self, data, extractor: JSONExtractor, tmp_path: Path):
        """Shared round-trip helper: extract → mock-translate → parse back."""
        import json as _json
        # 1) OPP extract
        src = tmp_path / "src.json"
        src.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = extractor.extract(src)

        # 2) Mock OL translate
        translated = self._mock_translate(result.paragraphs)

        # 3) Write translated MD and parse as JSON fence + kv for verification
        md_text = "\n\n".join(p.text for p in translated)

        # Extract base data from fence
        fence_start = md_text.find("```json\n")
        fence_end = md_text.find("\n```")
        assert fence_start >= 0 and fence_end > fence_start
        json_str = md_text[fence_start + len("```json\n"):fence_end]
        base = _json.loads(json_str)

        # Extract translations from kv lines
        translations: dict[str, str] = {}
        for line in md_text.splitlines():
            if line.startswith("json_field:"):
                _, rest = line.split("json_field:", 1)
                path, _, val = rest.partition(" = ")
                translations[path] = val

        return base, translations

    def test_roundtrip_simple(self, tmp_path: Path):
        data = {"name": "Alice", "city": "Belgrade"}
        extractor = JSONExtractor()
        base, translations = self._round_trip(data, extractor, tmp_path)

        assert base["name"] == "Alice"
        assert base["city"] == "Belgrade"
        assert translations["name"] == "Alice [TR]"
        assert translations["city"] == "Belgrade [TR]"

    def test_roundtrip_nested(self, tmp_path: Path):
        data = {"user": {"profile": {"name": "Alice", "bio": "dev"}}}
        extractor = JSONExtractor()
        base, translations = self._round_trip(data, extractor, tmp_path)

        assert base["user"]["profile"]["name"] == "Alice"
        assert translations["user.profile.name"] == "Alice [TR]"
        assert translations["user.profile.bio"] == "dev [TR]"

    def test_roundtrip_array(self, tmp_path: Path):
        data = {"items": ["first", "second", "third"]}
        extractor = JSONExtractor()
        base, translations = self._round_trip(data, extractor, tmp_path)

        assert base["items"] == ["first", "second", "third"]
        assert translations["items.0"] == "first [TR]"
        assert translations["items.1"] == "second [TR]"
        assert translations["items.2"] == "third [TR]"

    def test_roundtrip_mixed_types(self, tmp_path: Path):
        data = {
            "name": "Test",
            "count": 42,
            "active": True,
            "ratio": 3.14,
            "meta": None,
        }
        extractor = JSONExtractor()
        base, translations = self._round_trip(data, extractor, tmp_path)

        assert base["count"] == 42
        assert base["active"] is True
        assert base["ratio"] == 3.14
        assert base["meta"] is None
        # Only "name" is a string, only one kv entry
        assert set(translations.keys()) == {"name"}
        assert translations["name"] == "Test [TR]"

    def test_roundtrip_unicode(self, tmp_path: Path):
        data = {"title": "中文标题", "desc": "日本語の説明"}
        extractor = JSONExtractor()
        base, translations = self._round_trip(data, extractor, tmp_path)

        assert base["title"] == "中文标题"
        assert base["desc"] == "日本語の説明"
        assert translations["title"] == "中文标题 [TR]"
        assert translations["desc"] == "日本語の説明 [TR]"


class TestJSONExtractorXLIFF:
    """OPP#42: JSON --target-format xlf produces valid XLIFF 1.2."""

    def _run_opp_cli(self, json_data: dict, tmp_path: Path, target_format: str = "xlf") -> tuple[Path, str]:
        """Run opp CLI on a JSON file and return (xlf_path, content)."""
        import subprocess
        import sys
        import json as _json

        json_file = tmp_path / "test.json"
        json_file.write_text(_json.dumps(json_data, ensure_ascii=False), encoding="utf-8")

        output_dir = tmp_path / "out"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run([
            sys.executable, "-m", "opp.cli",
            str(json_file),
            "--target-format", target_format,
            "--source-lang", "en",
            "--target-lang", "zh",
            "--output-dir", str(output_dir),
        ], capture_output=True, text=True)

        assert result.returncode == 0, \
            f"CLI failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

        xlf_path = output_dir / "test.xlf"
        assert xlf_path.exists(), \
            f"XLIFF file not found at {xlf_path}"

        return xlf_path, xlf_path.read_text("utf-8")

    def test_json_extract_md_still_works(self, tmp_path: Path):
        """OPP#42: Existing MD path must remain unchanged."""
        import json as _json

        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "Alice", "value": 42}', encoding="utf-8")

        output_dir = tmp_path / "out_md"
        import subprocess, sys
        result = subprocess.run([
            sys.executable, "-m", "opp.cli",
            str(json_file),
            "--target-format", "md",
            "--output-dir", str(output_dir),
        ], capture_output=True, text=True)

        assert result.returncode == 0
        md_path = output_dir / "test.md"
        assert md_path.exists(), f"MD file not found: {md_path}"
        md_content = md_path.read_text("utf-8")
        assert "```json" in md_content, "MD should contain fenced code block"
        assert "Alice" in md_content, "MD should contain JSON values"

    def _get_trans_units(self, xliff_content: str) -> list[dict[str, str]]:
        """Parse XLIFF and extract trans-unit id + source pairs."""
        from lxml import etree
        root = etree.fromstring(xliff_content.encode("utf-8"))
        ns = {"x": "urn:oasis:names:tc:xliff:document:1.2"}
        units = []
        for tu in root.xpath("//x:trans-unit", namespaces=ns):
            unit_id = tu.get("id", "")
            source = tu.findtext("x:source", "", namespaces=ns)
            units.append({"id": unit_id, "source": source})
        return units

    def test_json_extract_xlf_produces_valid_xliff(self, tmp_path: Path):
        """OPP#42: Simple JSON produces valid XLIFF 1.2 with correct trans-units."""
        data = {"name": "Alice", "greeting": "Hello"}
        xlf_path, content = self._run_opp_cli(data, tmp_path)

        assert 'version="1.2"' in content, "Should be XLIFF 1.2"
        assert 'urn:oasis:names:tc:xliff:document:1.2' in content, "Should use 1.2 namespace"

        units = self._get_trans_units(content)
        assert len(units) == 2, f"Expected 2 trans-units, got {len(units)}"

        ids = {u["id"]: u["source"] for u in units}
        assert ids.get("name") == "Alice", f"Expected name=Alice, got {ids}"
        assert ids.get("greeting") == "Hello", f"Expected greeting=Hello, got {ids}"

    def test_json_extract_xlf_handles_nested_objects(self, tmp_path: Path):
        """OPP#42: Nested JSON emits all leaf values as flat dot-notation trans-units."""
        data = {
            "user": {
                "name": "Alice",
                "profile": {
                    "bio": "Developer",
                    "location": "Beijing",
                }
            },
            "settings": {
                "theme": "dark",
                "count": 42,
            }
        }
        xlf_path, content = self._run_opp_cli(data, tmp_path)
        units = self._get_trans_units(content)

        ids = {u["id"]: u["source"] for u in units}

        assert ids.get("user.name") == "Alice", f"Missing user.name: {ids}"
        assert ids.get("user.profile.bio") == "Developer", f"Missing user.profile.bio: {ids}"
        assert ids.get("user.profile.location") == "Beijing", f"Missing user.profile.location: {ids}"
        assert ids.get("settings.theme") == "dark", f"Missing settings.theme: {ids}"
        assert ids.get("settings.count") == "42", f"Missing settings.count (as str): {ids}"

    def test_json_extract_xlf_handles_arrays(self, tmp_path: Path):
        """OPP#42: JSON arrays with strings emit numeric-indexed trans-units."""
        data = {"items": ["first", "second", "third"]}
        xlf_path, content = self._run_opp_cli(data, tmp_path)
        units = self._get_trans_units(content)

        ids = {u["id"]: u["source"] for u in units}
        assert ids.get("items.0") == "first", f"Missing items.0: {ids}"
        assert ids.get("items.1") == "second", f"Missing items.1: {ids}"
        assert ids.get("items.2") == "third", f"Missing items.2: {ids}"

    def test_json_extract_xlf_includes_all_values(self, tmp_path: Path):
        """OPP#42: All leaf values (including numbers/bools) included as strings in XLIFF."""
        data = {
            "name": "Alice",
            "age": 30,
            "active": True,
            "score": 3.14,
        }
        xlf_path, content = self._run_opp_cli(data, tmp_path)
        units = self._get_trans_units(content)

        ids = {u["id"]: u["source"] for u in units}
        assert ids.get("name") == "Alice", f"Missing string value: {ids}"
        assert ids.get("age") == "30", f"Numeric value should be str '30': {ids}"
        assert ids.get("active") == "True", f"Bool value should be str 'True': {ids}"
        assert ids.get("score") == "3.14", f"Float value should be str '3.14': {ids}"

    def test_json_extract_xlf_target_format_both(self, tmp_path: Path):
        """OPP#42: --target-format both produces both MD and proper XLIFF."""
        import subprocess, sys, json as _json

        json_file = tmp_path / "test_both.json"
        json_file.write_text('{"key": "value"}', encoding="utf-8")

        output_dir = tmp_path / "out_both"
        result = subprocess.run([
            sys.executable, "-m", "opp.cli",
            str(json_file),
            "--target-format", "both",
            "--source-lang", "en",
            "--target-lang", "zh",
            "--output-dir", str(output_dir),
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        md_path = output_dir / "test_both.md"
        assert md_path.exists(), "MD file must exist for --target-format both"
        md_content = md_path.read_text("utf-8")
        assert "```json" in md_content, "MD should have fenced code block"

        xlf_path = output_dir / "test_both.xlf"
        assert xlf_path.exists(), "XLIFF file must exist for --target-format both"
        xlf_content = xlf_path.read_text("utf-8")
        assert 'version="1.2"' in xlf_content, "Should be XLIFF 1.2"

        units = self._get_trans_units(xlf_content)
        assert len(units) == 1, f"Expected 1 trans-unit, got {len(units)}"
        assert units[0]["id"] == "key"
        assert units[0]["source"] == "value"
