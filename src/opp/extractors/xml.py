from pathlib import Path
from typing import Any

from lxml import etree

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError


class XMLExtractor(ExtractorBase):
    def supported_extensions(self) -> list[str]:
        return [".xml"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            tree = etree.parse(str(input_path))
            root = tree.getroot()
        except etree.XMLSyntaxError as e:
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

    def extract_nodes(self, input_path: Path, xpath: str) -> list[dict[str, Any]]:
        """Extract nodes from XML using XPath expression.
        
        Args:
            input_path: Path to the XML file
            xpath: XPath expression to select nodes
            
        Returns:
            List of dicts with node data (tag, text, attributes, children)
        """
        self.validate_file(input_path)
        
        try:
            tree = etree.parse(str(input_path))
            root = tree.getroot()
        except etree.XMLSyntaxError as e:
            raise CorruptedFileError(f"XML解析失败（非 Well-Formed）: {input_path}: {e}")
        
        try:
            nodes = root.xpath(xpath)
        except etree.XPathSyntaxError as e:
            raise CorruptedFileError(f"XPath语法错误: {xpath}: {e}")
        except etree.XPathEvalError as e:
            raise CorruptedFileError(f"XPath执行错误: {xpath}: {e}")
        
        result = []
        for node in nodes:
            node_dict = self._node_to_dict(node)
            result.append(node_dict)
        
        return result

    def _node_to_dict(self, node: etree._Element) -> dict[str, Any]:
        """Convert an lxml element to a dict with tag, text, attributes, children."""
        children = []
        for child in node:
            children.append(self._node_to_dict(child))
        
        attributes = dict(node.attrib) if node.attrib else {}
        
        return {
            "tag": node.tag,
            "text": node.text if node.text else "",
            "attributes": attributes,
            "children": children,
        }

    def _build_namespace_map(self, root: etree._Element) -> dict[str, str]:
        namespace_map: dict[str, str] = {}
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
        element: etree._Element,
        namespace_map: dict[str, str],
        level: int | None = None,
    ) -> list[ParagraphData]:
        paragraphs: list[ParagraphData] = []

        if element.tag is etree.Comment:
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

    def _get_text_content(self, element: etree._Element) -> str:
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

    def _get_style_name(self, local_name: str, namespace_map: dict[str, str]) -> str:
        default_ns = namespace_map.get("default", "")
        if default_ns:
            return f"{default_ns}:{local_name}"
        return local_name
