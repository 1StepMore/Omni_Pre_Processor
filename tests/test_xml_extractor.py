import tempfile
from pathlib import Path

import pytest

from opp.extractors.xml import XMLExtractor
from opp.utils.exceptions import CorruptedFileError


class TestXMLExtractor:
    """Test XMLExtractor following Phase 5 UTDD matrix."""

    # ===== NORMAL CASES =====

    def test_extract_simple_config_xml(self, tmp_path: Path):
        """Normal: Simple configuration XML."""
        xml_file = tmp_path / "simple.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<config>\n'
            '  <setting name="host">localhost</setting>\n'
            '  <setting name="port">8080</setting>\n'
            '</config>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) >= 2

    def test_extract_simple_config_xml_values(self, tmp_path: Path):
        """Normal: Verify extracted text content."""
        xml_file = tmp_path / "simple.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<config>\n'
            '  <setting>localhost</setting>\n'
            '</config>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert any("localhost" in t for t in texts)

    def test_extract_namespaced_xml(self, tmp_path: Path):
        """Normal: XML with namespaces."""
        xml_file = tmp_path / "namespaced.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root xmlns:ns="http://example.com/ns">\n'
            '  <ns:element>Content</ns:element>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) >= 1

    def test_extract_namespaced_xml_preserves_namespace(self, tmp_path: Path):
        """Normal: Verify namespace is preserved in style."""
        xml_file = tmp_path / "namespaced.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root xmlns:ns="http://example.com/ns">\n'
            '  <ns:element>Content</ns:element>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        styles = [p.style for p in result.paragraphs if p.style]
        assert any("ns:element" in s or "element" in s for s in styles)

    def test_extract_attributes(self, tmp_path: Path):
        """Normal: XML with attributes."""
        xml_file = tmp_path / "attributes.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<config>\n'
            '  <item id="1" type="server">Server One</item>\n'
            '</config>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert any("Server One" in t for t in texts)

    def test_extract_mixed_content(self, tmp_path: Path):
        """Normal: XML with mixed content (text and elements)."""
        xml_file = tmp_path / "mixed.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<document>\n'
            '  <p>Hello <b>World</b>!</p>\n'
            '</document>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert any("Hello" in t and "World" in t for t in texts)

    def test_extract_multiple_root_children(self, tmp_path: Path):
        """Normal: Multiple sibling elements at root level."""
        xml_file = tmp_path / "siblings.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <item>First</item>\n'
            '  <item>Second</item>\n'
            '  <item>Third</item>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert "First" in texts
        assert "Second" in texts
        assert "Third" in texts

    def test_extract_default_namespace(self, tmp_path: Path):
        """Normal: XML with default namespace (no prefix)."""
        xml_file = tmp_path / "default_ns.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root xmlns="http://default.ns.example">\n'
            '  <element>Content</element>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) >= 1

    # ===== BOUNDARY CASES =====

    def test_extract_deep_nesting(self, tmp_path: Path):
        """Boundary: Deeply nested XML (10 levels)."""
        xml_file = tmp_path / "deep.xml"
        # Create 10 levels of nesting
        content = '<level1><level2><level3><level4><level5><level6><level7><level8><level9><level10>Deep</level10></level9></level8></level7></level6></level5></level4></level3></level2></level1>'
        xml_file.write_text(f'<?xml version="1.0"?>\n{content}\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert "Deep" in texts

    def test_extract_deep_nesting_at_boundary(self, tmp_path: Path):
        """Boundary: XML at exactly 100 nested levels."""
        xml_file = tmp_path / "deep100.xml"
        tag = "l"
        current = "<l1>Content</l1>"
        for i in range(2, 101):
            current = f"<l{i}>{current}</l{i}>"
        xml_file.write_text(f'<?xml version="1.0"?>\n<root>{current}</root>\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert "Content" in texts

    def test_extract_large_file_1000_nodes(self, tmp_path: Path):
        """Boundary: XML with exactly 1000 nodes."""
        xml_file = tmp_path / "large.xml"
        items = "".join(f"<item>Node{i}</item>" for i in range(1000))
        xml_file.write_text(f'<?xml version="1.0"?>\n<root>{items}</root>\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) == 1000

    def test_extract_large_file_1001_nodes(self, tmp_path: Path):
        """Boundary: XML with 1001 nodes (just over 1000)."""
        xml_file = tmp_path / "large1001.xml"
        items = "".join(f"<item>Node{i}</item>" for i in range(1001))
        xml_file.write_text(f'<?xml version="1.0"?>\n<root>{items}</root>\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) == 1001

    def test_extract_wide_at_boundary(self, tmp_path: Path):
        """Boundary: XML at exactly 100 sibling elements."""
        xml_file = tmp_path / "wide100.xml"
        items = "".join(f"<item>Item{i}</item>" for i in range(100))
        xml_file.write_text(f'<?xml version="1.0"?>\n<root>{items}</root>\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) == 100

    def test_extract_empty_root(self, tmp_path: Path):
        """Boundary: Empty root element."""
        xml_file = tmp_path / "empty.xml"
        xml_file.write_text('<?xml version="1.0"?>\n<root></root>\n')
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) == 0
        assert "文档为空" in result.warnings

    def test_extract_whitespace_only(self, tmp_path: Path):
        """Boundary: XML with only whitespace content."""
        xml_file = tmp_path / "whitespace.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '    \n'
            '  \n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) == 0

    # ===== EXCEPTION CASES =====

    def test_extract_malformed_xml(self, tmp_path: Path):
        """Exception: Malformed XML that cannot be parsed."""
        xml_file = tmp_path / "malformed.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <unclosed>\n'
            '  <another>text</another>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(xml_file)

    def test_extract_unclosed_tag(self, tmp_path: Path):
        """Exception: XML with unclosed tag."""
        xml_file = tmp_path / "unclosed.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <p>Paragraph without closing\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(xml_file)

    def test_extract_mismatched_tags(self, tmp_path: Path):
        """Exception: XML with mismatched opening/closing tags."""
        xml_file = tmp_path / "mismatched.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <outer><inner>text</outer></inner>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(xml_file)

    def test_extract_dtd_entity(self, tmp_path: Path):
        """Exception: XML with DTD entity (external entity)."""
        xml_file = tmp_path / "dtd.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE root [\n'
            '  <!ENTITY example "replaced">\n'
            ']>\n'
            '<root>&example;</root>\n'
        )
        extractor = XMLExtractor()
        # Should either raise or handle gracefully
        result = extractor.extract(xml_file)
        # Entity should be resolved or warned about
        assert result is not None

    def test_extract_oversized_attribute_value(self, tmp_path: Path):
        """Exception: XML with extremely large attribute value."""
        xml_file = tmp_path / "large_attr.xml"
        large_value = "x" * 100000
        xml_file.write_text(
            f'<?xml version="1.0"?>\n'
            f'<root attr="{large_value}">content</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert len(result.paragraphs) >= 1

    def test_extract_nonexistent_file(self):
        """Exception: Attempt to extract non-existent file."""
        extractor = XMLExtractor()
        with pytest.raises((CorruptedFileError, FileNotFoundError)):
            extractor.extract(Path("/nonexistent/file.xml"))

    def test_extract_binary_file(self, tmp_path: Path):
        """Exception: File containing binary data as XML."""
        xml_file = tmp_path / "binary.xml"
        xml_file.write_bytes(b'\x00\x01\x02\x03XML\x04\x05')
        extractor = XMLExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(xml_file)

    def test_extract_special_characters(self, tmp_path: Path):
        """Exception: XML with special characters that need escaping."""
        xml_file = tmp_path / "special.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <text>&lt;tag&gt; &amp; &quot;quote&quot;</text>\n'
            '</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert any("<tag>" in t for t in texts)
        assert any("&" in t for t in texts)

    def test_extract_encoding_declaration(self, tmp_path: Path):
        """Normal: XML with explicit encoding declaration."""
        xml_file = tmp_path / "encoded.xml"
        xml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<root>\n'
            '  <text>Hello 你好</text>\n'
            '</root>\n',
            encoding="utf-8"
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        texts = [p.text for p in result.paragraphs]
        assert any("Hello" in t for t in texts)
        assert any("你好" in t for t in texts)

    # ===== METADATA & STRUCTURE =====

    def test_supported_extensions(self):
        """Verify supported extensions returns .xml."""
        extractor = XMLExtractor()
        assert ".xml" in extractor.supported_extensions()

    def test_extract_returns_metadata(self, tmp_path: Path):
        """Verify extraction returns metadata."""
        xml_file = tmp_path / "meta.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>Content</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert result.metadata is not None
        assert result.metadata.file_size is not None

    def test_extract_returns_empty_tables(self, tmp_path: Path):
        """Verify XML extraction returns empty tables list."""
        xml_file = tmp_path / "tables.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>Content</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert result.tables == []

    def test_extract_returns_empty_images(self, tmp_path: Path):
        """Verify XML extraction returns empty images list."""
        xml_file = tmp_path / "images.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>Content</root>\n'
        )
        extractor = XMLExtractor()
        result = extractor.extract(xml_file)
        assert result.images == []

class TestXMLExtractorNodes:
    """Test XMLExtractor.extract_nodes() method - Phase 5."""

    def test_extract_nodes_xpath_query(self, tmp_path: Path):
        """XPath query selects correct nodes."""
        xml_file = tmp_path / "items.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <item>First</item>\n'
            '  <item>Second</item>\n'
            '  <item>Third</item>\n'
            '</root>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "//item")

        assert len(nodes) == 3
        assert nodes[0]["text"] == "First"
        assert nodes[1]["text"] == "Second"
        assert nodes[2]["text"] == "Third"

    def test_extract_nodes_with_attributes(self, tmp_path: Path):
        """Node attributes are extracted."""
        xml_file = tmp_path / "attrs.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<config>\n'
            '  <server id="1" type="primary">Main</server>\n'
            '  <server id="2" type="backup">Backup</server>\n'
            '</config>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "//server")

        assert len(nodes) == 2
        assert nodes[0]["attributes"]["id"] == "1"
        assert nodes[0]["attributes"]["type"] == "primary"
        assert nodes[0]["text"] == "Main"

    def test_extract_nodes_nested_elements(self, tmp_path: Path):
        """Nested elements are captured in children."""
        xml_file = tmp_path / "nested.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<parent>\n'
            '  <child>ChildText</child>\n'
            '</parent>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "//parent")

        assert len(nodes) == 1
        assert nodes[0]["tag"] == "parent"
        assert len(nodes[0]["children"]) == 1
        assert nodes[0]["children"][0]["tag"] == "child"
        assert nodes[0]["children"][0]["text"] == "ChildText"

    def test_extract_nodes_empty_result(self, tmp_path: Path):
        """XPath with no matches returns empty list."""
        xml_file = tmp_path / "simple.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <item>Content</item>\n'
            '</root>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "//nonexistent")

        assert nodes == []

    def test_extract_nodes_root_element(self, tmp_path: Path):
        """Selecting root element works."""
        xml_file = tmp_path / "root.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <child>Value</child>\n'
            '</root>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "/root")

        assert len(nodes) == 1
        assert nodes[0]["tag"] == "root"

    def test_extract_nodes_invalid_xpath(self, tmp_path: Path):
        """Invalid XPath raises error."""
        xml_file = tmp_path / "valid.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>Content</root>\n'
        )

        extractor = XMLExtractor()
        with pytest.raises(Exception):
            extractor.extract_nodes(xml_file, "//[invalid")

    def test_extract_nodes_wildcard_xpath(self, tmp_path: Path):
        """Wildcard XPath selects matching nodes."""
        xml_file = tmp_path / "wildcard.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <item id="1">A</item>\n'
            '  <other id="2">B</other>\n'
            '  <item id="3">C</item>\n'
            '</root>\n'
        )

        extractor = XMLExtractor()
        nodes = extractor.extract_nodes(xml_file, "//item")

        assert len(nodes) == 2
        assert nodes[0]["attributes"]["id"] == "1"
        assert nodes[1]["attributes"]["id"] == "3"
