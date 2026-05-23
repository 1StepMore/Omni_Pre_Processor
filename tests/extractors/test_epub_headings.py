"""Tests for EPUB heading extraction."""
from pathlib import Path
from typing import Generator

import pytest

from opp.extractors.epub import EPUBExtractor
from opp.utils.dataclasses import ParagraphData


def create_epub_with_ebooklib(tmp_path: Path, filename: str, chapters: list) -> Path:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(f'test-{filename}')
    book.set_title('Test EPUB')
    book.set_language('en')

    epub_chapters = []
    for i, (title, content) in enumerate(chapters):
        c = epub.EpubHtml(title=title, file_name=f'chapter{i+1}.xhtml', lang='en')
        c.content = content
        book.add_item(c)
        epub_chapters.append(c)

    book.spine = epub_chapters
    book.add_item(epub.EpubNav())

    epub_path = tmp_path / filename
    epub.write_epub(str(epub_path), book)
    return epub_path


@pytest.fixture
def epub_with_headings(tmp_path: Path) -> Path:
    """Create EPUB with various heading levels and body text."""
    return create_epub_with_ebooklib(
        tmp_path,
        'headings.epub',
        [
            ('Headings', '''<html><body>
                <h1>Main Title</h1>
                <p>First paragraph body text.</p>
                <h2>Subheading Level 2</h2>
                <p>Second paragraph body text.</p>
                <h3>Subheading Level 3</h3>
                <p>Third paragraph body text.</p>
                <h4>Subheading Level 4</h4>
                <p>Fourth paragraph body text.</p>
                <h5>Subheading Level 5</h5>
                <p>Fifth paragraph body text.</p>
                <h6>Subheading Level 6</h6>
                <p>Sixth paragraph body text.</p>
            </body></html>'''),
        ]
    )


@pytest.fixture
def epub_with_footnote_heading(tmp_path: Path) -> Path:
    """Create EPUB with heading containing footnote marker."""
    return create_epub_with_ebooklib(
        tmp_path,
        'footnote_heading.epub',
        [
            ('Footnote Heading', '''<html><body>
                <h1>Title with footnote marker<a href="#fn1" role="doc-noteref">[1]</a></h1>
                <p>Body text with footnote.<a href="#fn2" role="doc-noteref">[2]</a></p>
            </body></html>'''),
        ]
    )


class TestEPUBHeadingExtraction:

    def test_h1_extraction(self, epub_with_headings):
        """Given EPUB with h1 tag → expect ParagraphData with level=1, style='Heading 1'."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_headings)

        h1_paragraphs = [p for p in result.paragraphs if p.style == "Heading 1"]
        assert len(h1_paragraphs) >= 1, "Expected at least one Heading 1 paragraph"

        h1 = h1_paragraphs[0]
        assert h1.level == 1, f"Expected level=1, got level={h1.level}"
        assert h1.style == "Heading 1", f"Expected style='Heading 1', got style='{h1.style}'"
        assert "Main Title" in h1.text, f"Expected 'Main Title' in text, got '{h1.text}'"

    def test_h2_extraction(self, epub_with_headings):
        """Given EPUB with h2 tag → expect ParagraphData with level=2, style='Heading 2'."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_headings)

        h2_paragraphs = [p for p in result.paragraphs if p.style == "Heading 2"]
        assert len(h2_paragraphs) >= 1, "Expected at least one Heading 2 paragraph"

        h2 = h2_paragraphs[0]
        assert h2.level == 2, f"Expected level=2, got level={h2.level}"
        assert h2.style == "Heading 2", f"Expected style='Heading 2', got style='{h2.style}'"
        assert "Subheading Level 2" in h2.text, f"Expected 'Subheading Level 2' in text, got '{h2.text}'"

    def test_h3_extraction(self, epub_with_headings):
        """Given EPUB with h3 tag → expect ParagraphData with level=3, style='Heading 3'."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_headings)

        h3_paragraphs = [p for p in result.paragraphs if p.style == "Heading 3"]
        assert len(h3_paragraphs) >= 1, "Expected at least one Heading 3 paragraph"

        h3 = h3_paragraphs[0]
        assert h3.level == 3, f"Expected level=3, got level={h3.level}"
        assert h3.style == "Heading 3", f"Expected style='Heading 3', got style='{h3.style}'"
        assert "Subheading Level 3" in h3.text, f"Expected 'Subheading Level 3' in text, got '{h3.text}'"

    def test_body_text_extraction(self, epub_with_headings):
        """Given EPUB with body text → expect ParagraphData with level=None, style='Normal'."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_headings)

        normal_paragraphs = [p for p in result.paragraphs if p.style == "Normal"]
        assert len(normal_paragraphs) >= 1, "Expected at least one Normal paragraph"

        # Body text should have level=None and style="Normal"
        for p in normal_paragraphs:
            assert p.level is None, f"Expected level=None for body text, got level={p.level}"
            assert p.style == "Normal", f"Expected style='Normal', got style='{p.style}'"

    def test_no_markdown_heading_syntax(self, epub_with_headings):
        """Headings should NOT contain ## markdown syntax."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_headings)

        for p in result.paragraphs:
            # Text should not contain ## prefix for headings
            assert not p.text.startswith("## "), f"Heading text should not have ## prefix: '{p.text}'"

    def test_footnote_markers_preserved(self, epub_with_footnote_heading):
        """Footnote markers [[footnote]] should be preserved in heading text."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_with_footnote_heading)

        all_text = " ".join(p.text for p in result.paragraphs)
        # Footnote markers should be preserved
        assert "[[footnote]]" in all_text, f"Expected [[footnote]] marker in text, got: {all_text}"