import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    ExtractionResult,
    ParagraphData,
)


class JSONExtractor(ExtractorBase):
    MAX_DEPTH = 8

    def supported_extensions(self) -> list[str]:
        return [".json"]

    def _flatten(
        self,
        obj,
        prefix: str = "",
        depth: int = 0,
        result: dict[str, str] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, str]:
        if result is None:
            result = {}
        if warnings is None:
            warnings = []

        if depth > self.MAX_DEPTH:
            warnings.append(f"最大嵌套深度 {self.MAX_DEPTH} 已超出，截断路径: {prefix}")
            return result

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if value is None or (isinstance(value, str) and value == ""):
                    continue
                self._flatten(value, new_key, depth + 1, result, warnings)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_key = f"{prefix}.{idx}"
                if item is None or (isinstance(item, str) and item == ""):
                    continue
                self._flatten(item, new_key, depth + 1, result, warnings)
        else:
            result[prefix] = str(obj)

        return result


    def extract_key_values(self, input_path: Path) -> dict[str, Any]:
        """Extract key-value pairs from JSON file as a flat dictionary.

        Args:
            input_path: Path to JSON file

        Returns:
            Flat dictionary with dot-notation keys and actual leaf values
        """
        self.validate_file(input_path)

        with open(input_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        if isinstance(data, list):
            data = {"root": data}

        return self._flatten_to_any(data)

    def _flatten_to_any(
        self,
        obj,
        prefix: str = "",
        depth: int = 0,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Flatten nested JSON to dict with dot-notation keys, preserving value types."""
        if result is None:
            result = {}

        if depth > self.MAX_DEPTH:
            return result

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if value is None or (isinstance(value, str) and value == ""):
                    continue
                self._flatten_to_any(value, new_key, depth + 1, result)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_key = f"{prefix}.{idx}"
                if item is None or (isinstance(item, str) and item == ""):
                    continue
                self._flatten_to_any(item, new_key, depth + 1, result)
        else:
            result[prefix] = obj

        return result

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        with open(input_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        # Present JSON as a fenced code block (preserves structure, handles arbitrary nesting)
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        paragraphs = [ParagraphData(text=f"```json\n{pretty}\n```")]

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=metadata,
            warnings=warnings,
        )