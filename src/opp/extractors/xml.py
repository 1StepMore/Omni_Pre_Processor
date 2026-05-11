import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError


class XMLExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".xml"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            tree = ET.parse(input_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise CorruptedFileError(f"XML解析失败（非 Well-Formed）: {input_path}: {e}")

        namespace_map = self._build_namespace_map(root)
        paragraphs = self._extract_element(root, namespace_map)

        if not paragraphs:
            warnings.append("文档为空")

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=metadata,
            warnings=warnings,
        )

    def _build_namespace_map(self, root: ET.Element) -> Dict[str, str]:
        namespace_map: Dict[str, str] = {}
        for elem in root.iter():
            tag = elem.tag
            if tag.startswith("{"):
                uri = tag[1:tag.index("}")]
                namespace_map["_uri"] = uri
            for key, value in elem.attrib.items():
                if key.startswith("xmlns"):
                    if key == "xmlns":
                        namespace_map["default"] = value
                    elif key.startswith("xmlns:"):
                        prefix = key[6:]
                        namespace_map[prefix] = value
        return namespace_map

    def _extract_element(
        self,
        element: ET.Element,
        namespace_map: Dict[str, str],
        level: Optional[int] = None,
    ) -> List[ParagraphData]:
        paragraphs: List[ParagraphData] = []

        if element.tag is ET.Comment:
            return paragraphs

        text_content = self._get_text_content(element)

        if element.text and element.text.strip():
            tag_name = self._get_local_name(element.tag)
            style = self._get_style_name(tag_name, namespace_map)
            paragraphs.append(ParagraphData(
                text=text_content.strip(),
                style=style,
                level=level,
            ))

        for child in element:
            child_paragraphs = self._extract_element(child, namespace_map, level=level)
            paragraphs.extend(child_paragraphs)

        return paragraphs

    def _get_text_content(self, element: ET.Element) -> str:
        parts = []
        if element.text:
            parts.append(element.text)
        for child in element:
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    def _get_local_name(self, tag: str) -> str:
        if tag.startswith("{"):
            uri, local_name = tag[1:].split("}", 1)
            return local_name
        return tag

    def _get_style_name(self, local_name: str, namespace_map: Dict[str, str]) -> str:
        default_ns = namespace_map.get("default", "")
        if default_ns:
            return f"{default_ns}:{local_name}"
        return local_name
