import re

from opp.chunker import (
    BOUNDARY_CONFIDENCE_EXPLICIT,
    BOUNDARY_CONFIDENCE_INFERRED,
    CONTINUITY_CONTINUOUS,
    CONTINUITY_DISCONTINUOUS,
    ChunkMetaBuilder,
)
from opp.markdown.generator import MarkdownGenerator
from opp.utils.dataclasses import ExtractionResult, ParagraphData


class TestChunkMetaBuilder:
    """Unit tests for ChunkMetaBuilder.build()"""

    def test_build_with_single_chapter(self):
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

    def test_build_with_multiple_chapters(self):
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

    def test_build_with_no_chapter(self):
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

    def test_build_verifies_char_count(self):
        """build() should compute char_count as sum of text lengths for each chunk."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="Hello", chapter="Test"),
            ParagraphData(text="World", chapter="Test"),
        ]
        result = builder.build(paragraphs, "md5hash")

        expected_char_count = len("Hello") + len("World")
        assert result.chunks[0].char_count == expected_char_count

    def test_build_verifies_no_splitting(self):
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


class TestChapterMetaThreading:
    """OPP#116 M2: chapter_id threads through ChunkMeta; cross-chapter aggregation stays traceable."""

    def test_chapter_id_threads_through_chunks(self):
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="Intro text", chapter="Introduction"),
            ParagraphData(text="Chapter A content", chapter="Chapter A"),
            ParagraphData(text="More Chapter A content", chapter="Chapter A"),
            ParagraphData(text="Chapter B content", chapter="Chapter B"),
        ]
        result = builder.build(paragraphs, "md5-1")

        # One chunk per document-order run: Chapter A's two contiguous
        # paragraphs are a single run sharing ch-002.
        assert len(result.chunks) == 3
        assert [c.chapter_id for c in result.chunks] == ["ch-001", "ch-002", "ch-003"]
        assert [m.chapter_id for m in result.chapters] == ["ch-001", "ch-002", "ch-003"]
        assert [m.title for m in result.chapters] == ["Introduction", "Chapter A", "Chapter B"]

    def test_discontinuous_chapter_keeps_one_chapter_id(self):
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="A first", chapter="Chapter A"),
            ParagraphData(text="B only", chapter="Chapter B"),
            ParagraphData(text="A second", chapter="Chapter A"),
        ]
        result = builder.build(paragraphs, "md5-2")

        # Three document-order runs, but chapter A's runs share one chapter_id
        assert len(result.chunks) == 3
        assert result.chunks[0].chapter_id == result.chunks[2].chapter_id
        assert result.chunks[1].chapter_id != result.chunks[0].chapter_id

        meta_a = next(m for m in result.chapters if m.title == "Chapter A")
        assert meta_a.continuity == CONTINUITY_DISCONTINUOUS
        assert meta_a.paragraph_count == 2
        meta_b = next(m for m in result.chapters if m.title == "Chapter B")
        assert meta_b.continuity == CONTINUITY_CONTINUOUS

    def test_cross_chapter_aggregation_by_chapter_id(self):
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="A-one", chapter="A"),
            ParagraphData(text="B-one", chapter="B"),
            ParagraphData(text="A-two", chapter="A"),
            ParagraphData(text="A-three", chapter="A"),
            ParagraphData(text="B-two", chapter="B"),
        ]
        result = builder.build(paragraphs, "md5-3")

        # Aggregating chunks by chapter_id reconstructs each chapter's text volume
        aggregated: dict[str, int] = {}
        for chunk in result.chunks:
            aggregated[chunk.chapter_id] = aggregated.get(chunk.chapter_id, 0) + chunk.char_count
        by_title = {m.title: aggregated[m.chapter_id] for m in result.chapters}
        assert by_title == {
            "A": len("A-one") + len("A-two") + len("A-three"),
            "B": len("B-one") + len("B-two"),
        }
        assert result.total_chars == sum(len(p.text) for p in paragraphs)

    def test_char_offsets_stay_monotonic_across_runs(self):
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="A first", chapter="A"),
            ParagraphData(text="B only", chapter="B"),
            ParagraphData(text="A second", chapter="A"),
        ]
        result = builder.build(paragraphs, "md5-4")

        positions = [(c.start_char, c.end_char) for c in result.chunks]
        assert positions[0][1] == positions[1][0]
        assert positions[1][1] == positions[2][0]
        assert all(
            end - start == chunk.char_count
            for chunk, (start, end) in zip(result.chunks, positions)
        )


class TestChapterBoundaryQuality:
    """OPP#116 M2: boundary confidence + continuity annotations (annotation presence only)."""

    def test_explicit_chapter_gets_full_confidence(self):
        builder = ChunkMetaBuilder()
        result = builder.build([ParagraphData(text="H", chapter="Real Chapter")], "md5")
        assert result.chapters[0].boundary_confidence == BOUNDARY_CONFIDENCE_EXPLICIT
        assert result.chunks[0].boundary_confidence == BOUNDARY_CONFIDENCE_EXPLICIT

    def test_inferred_untitled_gets_reduced_confidence(self):
        builder = ChunkMetaBuilder()
        result = builder.build([ParagraphData(text="plain", chapter=None)], "md5")
        assert result.chapters[0].title == "Untitled"
        assert result.chapters[0].boundary_confidence == BOUNDARY_CONFIDENCE_INFERRED
        assert result.chunks[0].boundary_confidence == BOUNDARY_CONFIDENCE_INFERRED

    def test_confidence_is_pure_annotation_presence(self):
        """Confidence must not depend on text content, length, or position."""
        builder = ChunkMetaBuilder()
        paragraphs = [
            ParagraphData(text="x" * 100, chapter="T"),
            ParagraphData(text="y", chapter=None),
            ParagraphData(text="z", chapter="T"),
        ]
        result = builder.build(paragraphs, "md5")
        conf = {m.title: m.boundary_confidence for m in result.chapters}
        assert conf == {"T": BOUNDARY_CONFIDENCE_EXPLICIT, "Untitled": BOUNDARY_CONFIDENCE_INFERRED}


class TestChapterMetaMarkdownConsistency:
    """OPP#116 M2 acceptance anchor: MD chapter comments and ChunkMeta agree."""

    def test_md_chapter_comments_match_explicit_chapters(self):
        paragraphs = [
            ParagraphData(text="Front matter", chapter=None, position=0),
            ParagraphData(text="Alpha", chapter="Chapter Alpha", level=1, position=1),
            ParagraphData(text="Alpha body", chapter="Chapter Alpha", position=2),
            ParagraphData(text="Beta", chapter="Chapter Beta", level=1, position=3),
            ParagraphData(text="Gamma", chapter="Chapter Gamma", level=1, position=4),
        ]
        result = ChunkMetaBuilder().build(paragraphs, "md5-md")

        md = MarkdownGenerator().generate(
            ExtractionResult(paragraphs=paragraphs, tables=[], images=[])
        )
        md_chapters = re.findall(r"<!-- chapter: (.+?) -->", md)

        # Explicit chapters, in first-occurrence order; the inferred
        # "Untitled" group never emits a comment.
        expected = [
            m.title for m in result.chapters
            if m.boundary_confidence == BOUNDARY_CONFIDENCE_EXPLICIT
        ]
        assert md_chapters == expected

    def test_untitled_group_never_appears_in_md_comments(self):
        paragraphs = [
            ParagraphData(text="plain one", chapter=None, position=0),
            ParagraphData(text="plain two", chapter=None, position=1),
        ]
        result = ChunkMetaBuilder().build(paragraphs, "md5-u")
        assert [m.title for m in result.chapters] == ["Untitled"]

        md = MarkdownGenerator().generate(
            ExtractionResult(paragraphs=paragraphs, tables=[], images=[])
        )
        assert "<!-- chapter:" not in md
