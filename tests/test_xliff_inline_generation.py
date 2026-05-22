from opp.xliff.generator import XLIFFFileGenerator
from opp.utils.dataclasses import RunData


class TestXLIFFInlineGeneration:
    def test_encode_inline_elements_bold(self):
        runs = [
            RunData(text="Hello "),
            RunData(text="World", bold=True),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert '<bx id="1" type="bold"/>' in source
        assert '<ex id="1"/>' in source
        assert elements[0].type == "bold"

    def test_encode_inline_elements_italic(self):
        runs = [
            RunData(text="Hello "),
            RunData(text="World", italic=True),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert '<bx id="1" type="italic"/>' in source
        assert '<ex id="1"/>' in source
        assert elements[0].type == "italic"

    def test_encode_inline_elements_underline(self):
        runs = [
            RunData(text="Hello "),
            RunData(text="World", underline=True),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert '<bx id="1" type="underline"/>' in source
        assert '<ex id="1"/>' in source
        assert elements[0].type == "underline"

    def test_encode_inline_elements_strike(self):
        runs = [
            RunData(text="Hello "),
            RunData(text="World", strike=True),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert '<bx id="1" type="strike"/>' in source
        assert '<ex id="1"/>' in source
        assert elements[0].type == "strike"

    def test_encode_inline_elements_combined(self):
        runs = [
            RunData(text="Hello "),
            RunData(text="World", bold=True, italic=True),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert '<bx id="1" type="bold,italic"/>' in source
        assert '<ex id="1"/>' in source
        assert elements[0].type == "bold,italic"

    def test_encode_inline_elements_no_formatting(self):
        runs = [
            RunData(text="Hello World"),
        ]
        source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
        assert source == "Hello World"
        assert len(elements) == 0

    def test_escape_xml_preserves_bx_tags(self):
        text = 'Hello <bx id="1" type="bold"/>World<ex id="1"/>'
        escaped = XLIFFFileGenerator._escape_xml_for_xliff(text)
        assert '<bx' in escaped
        assert '&lt;bx' not in escaped

    def test_escape_xml_preserves_ex_tags(self):
        text = 'Hello <bx id="1" type="bold"/>World<ex id="1"/>'
        escaped = XLIFFFileGenerator._escape_xml_for_xliff(text)
        assert '<ex' in escaped
        assert '&lt;ex' not in escaped

    def test_escape_xml_preserves_g_tags(self):
        text = 'Hello <g id="1">World</g>'
        escaped = XLIFFFileGenerator._escape_xml_for_xliff(text)
        assert '<g id="1">' in escaped
        assert '&lt;g' not in escaped

    def test_escape_xml_normal_chars_escaped(self):
        text = 'Hello & World <tag>'
        escaped = XLIFFFileGenerator._escape_xml_for_xliff(text)
        assert '&amp;' in escaped
        assert '&lt;' in escaped
        assert '&gt;' in escaped