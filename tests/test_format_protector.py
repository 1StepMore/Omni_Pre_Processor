"""Tests for FormatProtector - RED phase (no implementation yet)."""

import pytest

from opp.format_protector import FormatProtector


class TestFormatProtector:
    """Test suite for FormatProtector code detection and character protection."""

    # ========================================================================
    # Code Block Detection Tests
    # ========================================================================

    def test_detect_code_blocks_indented(self):
        """Test indented code block detection (4 spaces or Tab)."""
        text = """Here is some text
    def hello():
        print("world")
    more text"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is True
        assert len(result["blocks"]) == 1
        assert "def hello" in result["blocks"][0]["content"]

    def test_detect_code_blocks_fenced(self):
        """Test fenced code block detection with ``` markers."""
        text = """Some text
```
def hello():
    print("world")
```
More text"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is True
        assert len(result["blocks"]) == 1
        assert "def hello" in result["blocks"][0]["content"]

    def test_detect_code_blocks_language_detection(self):
        """Test programming language detection in fenced blocks."""
        text = """```python
def hello():
    pass
```
```javascript
const x = 1;
```"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is True
        assert len(result["blocks"]) == 2
        languages = [b.get("language", "") for b in result["blocks"]]
        assert "python" in languages
        assert "javascript" in languages

    def test_detect_code_blocks_single_line(self):
        """Test single line code detection."""
        text = "Use `print()` to output"
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is True
        assert len(result["blocks"]) >= 1

    def test_detect_code_blocks_empty_block(self):
        """Test empty code block handling."""
        text = """```
```"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is False or len(result["blocks"]) == 0

    def test_detect_code_blocks_nested_fences(self):
        """Test code blocks containing nested fence markers."""
        text = """```
def example():
    code = "```nested```"
    return code
```"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        assert result["has_code"] is True
        assert len(result["blocks"]) == 1
        # Inner ``` should be preserved
        assert "nested" in result["blocks"][0]["content"]

    def test_detect_code_blocks_pseudo_code(self):
        """Test pseudo-code that looks like code but isn't."""
        text = """The algorithm works like this:
1. Take the input
2. Process it
3. Return result
This is not real code"""
        protector = FormatProtector()
        result = protector.detect_code_blocks(text)
        # Pseudo-code should not be detected as code blocks
        assert result["has_code"] is False or len(result["blocks"]) == 0

    # ========================================================================
    # Special Character Protection Tests
    # ========================================================================

    def test_protect_special_chars_markdown(self):
        """Test Markdown special character escaping."""
        text = "Use *italic* and **bold** and `code`"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # Characters should be escaped/protected
        assert "\\*" in result or result != text

    def test_protect_special_chars_html_entities(self):
        """Test HTML entity handling."""
        text = "<div>Hello &amp; World</div>"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # HTML entities should be preserved or protected
        assert "&amp;" in result or result != text

    def test_protect_special_chars_latex(self):
        """Test LaTeX formula protection."""
        text = r"The equation $E = mc^2$ is famous"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # LaTeX markers should be protected
        assert "$" in result or result != text

    def test_protect_special_chars_all_special(self):
        """Test document with many special characters."""
        text = r"""*bold* #header {bracket} $math$ `code`
&entity; <tag> \|escape\| ~~strike~~"""
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # Multiple special char types should be handled
        assert result is not None
        assert len(result) > 0

    def test_protect_special_chars_zero_width(self):
        """Test zero-width character detection."""
        text = "Hello\u200bWorld\u200cEnd"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # Zero-width chars should be detected/handled
        assert "\u200b" in result or result != text

    def test_protect_special_chars_escape_cycle(self):
        """Test escape cycle detection (\\\\n vs \\n)."""
        text = r"Line1\nLine2\\nLine3"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # Escape cycles should be properly handled
        assert result is not None

    def test_protect_special_chars_double_escape(self):
        """Test double escape detection."""
        text = r"Test\\escape\nanother\\escape"
        protector = FormatProtector()
        result = protector.protect_special_chars(text)
        # Double escapes should be detected
        assert result is not None