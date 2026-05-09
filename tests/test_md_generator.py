"""Tests for MarkdownGenerator - RED phase (implementation not yet exists)."""

import pytest
from pathlib import Path

from opp.utils.dataclasses import ParagraphData, TableData
from opp.markdown.generator import MarkdownGenerator  # Will fail until implemented


class TestMarkdownGenerator:
    """Test suite for MarkdownGenerator markdown generation methods."""

    # =========================================================================
    # Heading Generation Tests
    # =========================================================================

    def test_generate_headings_h1_h6(self):
        """H1-H6 heading generation."""
        paragraphs = [
            ParagraphData(text="Heading 1", style="Heading 1", level=1),
            ParagraphData(text="Heading 2", style="Heading 2", level=2),
            ParagraphData(text="Heading 3", style="Heading 3", level=3),
            ParagraphData(text="Heading 4", style="Heading 4", level=4),
            ParagraphData(text="Heading 5", style="Heading 5", level=5),
            ParagraphData(text="Heading 6", style="Heading 6", level=6),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs)
        expected = "# Heading 1\n## Heading 2\n### Heading 3\n#### Heading 4\n##### Heading 5\n###### Heading 6"
        assert result == expected

    def test_generate_headings_numbered(self):
        """Numbered heading generation."""
        paragraphs = [
            ParagraphData(text="Chapter 1", style="Heading 1", level=1),
            ParagraphData(text="Section 1.1", style="Heading 2", level=2),
            ParagraphData(text="Section 1.2", style="Heading 2", level=2),
            ParagraphData(text="Chapter 2", style="Heading 1", level=1),
            ParagraphData(text="Section 2.1", style="Heading 2", level=2),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs)
        expected = "# Chapter 1\n## Section 1.1\n## Section 1.2\n# Chapter 2\n## Section 2.1"
        assert result == expected

    def test_generate_headings_custom_style_mapping(self):
        """Custom style to heading level mapping."""
        paragraphs = [
            ParagraphData(text="Title", style="Title", level=0),
            ParagraphData(text="Subtitle", style="Subtitle", level=0),
            ParagraphData(text="Section A", style="Heading", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs, style_mapping={"Title": 1, "Subtitle": 2, "Heading": 3})
        expected = "# Title\n## Subtitle\n### Section A"
        assert result == expected

    def test_generate_headings_single_level(self):
        """Single level heading generation."""
        paragraphs = [
            ParagraphData(text="Only Heading", style="Heading 1", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs)
        expected = "# Only Heading"
        assert result == expected

    def test_generate_headings_empty_level(self):
        """Skip paragraphs with empty level."""
        paragraphs = [
            ParagraphData(text="Valid Heading", style="Heading 1", level=1),
            ParagraphData(text="No Level Text", style="Normal", level=None),
            ParagraphData(text="Another Heading", style="Heading 2", level=2),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs)
        expected = "# Valid Heading\n## Another Heading"
        assert result == expected

    def test_generate_headings_deep_level(self):
        """Level deeper than 6 should degrade to H6."""
        paragraphs = [
            ParagraphData(text="Deep Level 7", style="Heading 7", level=7),
            ParagraphData(text="Deep Level 10", style="Heading 10", level=10),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_headings(paragraphs)
        expected = "###### Deep Level 7\n###### Deep Level 10"
        assert result == expected

    # =========================================================================
    # List Generation Tests
    # =========================================================================

    def test_generate_lists_ordered(self):
        """Ordered list generation."""
        paragraphs = [
            ParagraphData(text="First item", style="List Number", level=1),
            ParagraphData(text="Second item", style="List Number", level=1),
            ParagraphData(text="Third item", style="List Number", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "1. First item\n2. Second item\n3. Third item"
        assert result == expected

    def test_generate_lists_unordered(self):
        """Unordered list generation."""
        paragraphs = [
            ParagraphData(text="Bullet A", style="List Bullet", level=1),
            ParagraphData(text="Bullet B", style="List Bullet", level=1),
            ParagraphData(text="Bullet C", style="List Bullet", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "- Bullet A\n- Bullet B\n- Bullet C"
        assert result == expected

    def test_generate_lists_nested(self):
        """Nested list generation (mixed)."""
        paragraphs = [
            ParagraphData(text="Item 1", style="List Bullet", level=1),
            ParagraphData(text="Subitem 1.1", style="List Bullet", level=2),
            ParagraphData(text="Subitem 1.2", style="List Bullet", level=2),
            ParagraphData(text="Item 2", style="List Bullet", level=1),
            ParagraphData(text="Subitem 2.1", style="List Number", level=2),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "- Item 1\n  - Subitem 1.1\n  - Subitem 1.2\n- Item 2\n  1. Subitem 2.1"
        assert result == expected

    def test_generate_lists_single_item(self):
        """Single item list generation."""
        paragraphs = [
            ParagraphData(text="Only One", style="List Bullet", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "- Only One"
        assert result == expected

    def test_generate_lists_empty_items(self):
        """Empty list items should be skipped."""
        paragraphs = [
            ParagraphData(text="Valid item", style="List Bullet", level=1),
            ParagraphData(text="", style="List Bullet", level=1),
            ParagraphData(text="Another valid", style="List Bullet", level=1),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "- Valid item\n- Another valid"
        assert result == expected

    def test_generate_lists_deep_nesting(self):
        """Nesting deeper than 10 should degrade to flat list."""
        paragraphs = [
            ParagraphData(text="Level 5", style="List Bullet", level=5),
            ParagraphData(text="Level 12", style="List Bullet", level=12),
            ParagraphData(text="Level 15", style="List Bullet", level=15),
        ]
        generator = MarkdownGenerator()
        result = generator.generate_lists(paragraphs)
        expected = "- Level 5\n- Level 12\n- Level 15"
        assert result == expected

    # =========================================================================
    # Table Generation Tests
    # =========================================================================

    def test_generate_tables_md_standard(self):
        """Standard markdown table generation."""
        table = TableData(
            headers=["Name", "Age", "City"],
            rows=[
                ["Alice", "30", "NYC"],
                ["Bob", "25", "LA"],
            ]
        )
        generator = MarkdownGenerator()
        result = generator.generate_tables_md([table])
        expected = "| Name | Age | City |\n|------|-----|------|\n| Alice | 30 | NYC |\n| Bob | 25 | LA |"
        assert result == expected

    def test_generate_tables_md_alignment(self):
        """Table alignment specification."""
        table = TableData(
            headers=["Left", "Center", "Right"],
            rows=[["a", "b", "c"]]
        )
        generator = MarkdownGenerator()
        result = generator.generate_tables_md([table], alignment=["left", "center", "right"])
        expected = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |"
        assert result == expected

    def test_generate_tables_md_header_detection(self):
        """Table header detection."""
        table = TableData(
            headers=["Column1", "Column2"],
            rows=[["data1", "data2"]]
        )
        generator = MarkdownGenerator()
        result = generator.generate_tables_md([table], has_header=True)
        expected = "| Column1 | Column2 |\n|---------|---------|\n| data1 | data2 |"
        assert result == expected

    def test_generate_tables_md_single_cell(self):
        """1x1 table generation."""
        table = TableData(
            headers=["Only"],
            rows=[["One"]]
        )
        generator = MarkdownGenerator()
        result = generator.generate_tables_md([table])
        expected = "| Only |\n|------|\n| One |"
        assert result == expected

    def test_generate_tables_md_wide(self):
        """Wide table with more than 10 columns."""
        headers = [f"Col{i}" for i in range(12)]
        row = [f"Val{i}" for i in range(12)]
        table = TableData(headers=headers, rows=[row])
        generator = MarkdownGenerator()
        result = generator.generate_tables_md([table])
        header_line = "| " + " | ".join(headers) + " |"
        sep_cells = ["------" if len(h) == 4 else "-------" for h in headers]
        sep_line = "|" + "|".join(sep_cells) + "|"
        data_line = "| " + " | ".join(row) + " |"
        expected = f"{header_line}\n{sep_line}\n{data_line}"
        assert result == expected
