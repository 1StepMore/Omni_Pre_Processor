import pytest

from opp.chunker import ChunkMetaBuilder, Chunk
from opp.utils.dataclasses import ParagraphData


class TestChunkMetaBuilder:
    """Unit tests for ChunkMetaBuilder.build()"""

    def build_with_single_chapter(self):
        """build() should group paragraphs by chapter - single chapter case."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="First paragraph", chapter="Chapter 1"),
            ParagraphData(text="Second paragraph", chapter="Chapter 1"),
            ParagraphData(text="Third paragraph", chapter="Chapter 1"),
        ]
        result = builder.build(paragraphs, "abc123")
        
        assert len(result.chunks) == 1
        assert result.chunks[0].title == "Chapter 1"
        assert result.chunks[0].char_count == sum(len(p.text) for p in paragraphs)

    def build_with_multiple_chapters(self):
        """build() should create separate chunks for different chapters."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="Intro text", chapter="Introduction"),
            ParagraphData(text="Chapter A content", chapter="Chapter A"),
            ParagraphData(text="More Chapter A content", chapter="Chapter A"),
            ParagraphData(text="Chapter B content", chapter="Chapter B"),
        ]
        result = builder.build(paragraphs, "def456")
        
        assert len(result.chunks) == 3
        chapter_titles = {chunk.title for chunk in result.chunks}
        assert chapter_titles == {"Introduction", "Chapter A", "Chapter B"}

    def build_with_no_chapter(self):
        """build() should group paragraphs with chapter=None together under 'Untitled'."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="First untitled", chapter=None),
            ParagraphData(text="Second untitled", chapter=None),
            ParagraphData(text="Third untitled", chapter=None),
        ]
        result = builder.build(paragraphs, "xyz789")
        
        assert len(result.chunks) == 1
        assert result.chunks[0].title == "Untitled"
        assert result.chunks[0].char_count == sum(len(p.text) for p in paragraphs)

    def build_verifies_char_count(self):
        """build() should compute char_count as sum of text lengths for each chunk."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="Hello", chapter="Test"),
            ParagraphData(text="World", chapter="Test"),
        ]
        result = builder.build(paragraphs, "md5hash")
        
        expected_char_count = len("Hello") + len("World")
        assert result.chunks[0].char_count == expected_char_count

    def build_verifies_no_splitting(self):
        """build() should not implement splitting logic - no max_chunk_size parameter."""
        builder = ChunkMetaBuilder()
        
        # Verify build method signature has no splitting-related parameters
        import inspect
        sig = inspect.signature(builder.build)
        param_names = list(sig.parameters.keys())
        
        assert "max_chunk_size" not in param_names
        assert "chunk_size" not in param_names
        assert "max_chars" not in param_names
        assert "split_at" not in param_names
        
        # Also verify the method documentation states no splitting logic
        assert "does NOT implement splitting logic" in builder.build.__doc__
        assert "only groups paragraphs by chapter" in builder.build.__doc__
