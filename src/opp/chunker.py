from collections import Counter
from dataclasses import dataclass, field

from opp.utils.dataclasses import DocumentMetadata, ParagraphData

# Chapter boundary confidence, derived ONLY from annotation presence so the
# value stays deterministic (OPP records structure; semantic boundary
# decisions remain downstream — Pipeline/OLL):
#   1.0  the extractor annotated the chapter title (``ParagraphData.chapter``)
#   0.5  no annotation — the run is inferred and grouped under "Untitled"
BOUNDARY_CONFIDENCE_EXPLICIT = 1.0
BOUNDARY_CONFIDENCE_INFERRED = 0.5

# Continuity of a chapter's paragraphs in document order:
#   continuous     the chapter is exactly one run
#   discontinuous  the title re-appears after a different chapter broke the run
CONTINUITY_CONTINUOUS = "continuous"
CONTINUITY_DISCONTINUOUS = "discontinuous"

# Sentinel title for paragraphs the extractor left unannotated. Chapters the
# extractor literally titles "Untitled" share this sentinel (documented trade-off).
UNTITLED = "Untitled"


@dataclass
class ChapterMeta:
    """Boundary-level metadata for one chapter (OPP#116 M2).

    ``chapter_id`` is the stable handle threaded through every :class:`Chunk`
    so cross-chapter aggregation stays traceable even when a chapter is split
    into several document-order runs (``continuity`` = ``discontinuous``).
    """

    chapter_id: str
    title: str
    boundary_confidence: float
    continuity: str
    paragraph_count: int


@dataclass
class Chunk:
    """Represents a chunk of text with its metadata."""

    index: int
    title: str | None
    start_char: int
    end_char: int
    char_count: int
    source_md5: str
    # OPP#116 M2: stable chapter handle + boundary confidence, set by
    # ChunkMetaBuilder (defaults keep hand-built Chunks valid).
    chapter_id: str | None = None
    boundary_confidence: float | None = None


@dataclass
class ChunkedResult:
    """Result of chunking operation with metadata."""

    chunks: list[Chunk]
    total_chars: int
    estimated_chunks: int
    metadata: DocumentMetadata
    # OPP#116 M2: one entry per distinct chapter, in first-occurrence order.
    chapters: list[ChapterMeta] = field(default_factory=list)


class ChunkMetaBuilder:
    """Builds chunk metadata by grouping paragraphs by chapter.

    Note: This class only groups by chapter and computes metadata.
    Actual chunk boundary splitting is handled by Pipeline/OLL.
    """

    def build(self, paragraphs: list[ParagraphData], source_md5: str) -> ChunkedResult:
        """Build chunk metadata from paragraphs grouped by chapter.

        Args:
            paragraphs: List of ParagraphData to process
            source_md5: MD5 hash of the source document

        Returns:
            ChunkedResult with one chunk per document-order chapter run,
            one :class:`ChapterMeta` per distinct chapter (boundary confidence
            + continuity, OPP#116 M2) and computed metadata. Chunks of a
            discontinuous chapter share its ``chapter_id`` so aggregation by
            chapter stays traceable.

        Note:
            This method does NOT implement splitting logic.
            It only groups paragraphs by chapter and computes metadata.
            Actual chunk boundary determination is done by Pipeline/OLL.
        """
        # Split the stream into document-order runs: a run breaks when the
        # annotated title changes. A title re-appearing after a different
        # chapter starts a NEW run that shares the same chapter_id, so a
        # discontinuous chapter stays visible instead of being silently
        # merged (the pre-M2 title-keyed dict grouping hid it).
        runs: list[tuple[str, list[ParagraphData]]] = []
        for p in paragraphs:
            title = p.chapter if p.chapter else UNTITLED
            if runs and runs[-1][0] == title:
                runs[-1][1].append(p)
            else:
                runs.append((title, [p]))

        run_counts: Counter[str] = Counter(title for title, _ in runs)

        # One ChapterMeta per distinct chapter, in first-occurrence order.
        chapters: list[ChapterMeta] = []
        chapter_ids: dict[str, str] = {}
        for title in run_counts:
            chapter_id = f"ch-{len(chapter_ids) + 1:03d}"
            chapter_ids[title] = chapter_id
            chapters.append(ChapterMeta(
                chapter_id=chapter_id,
                title=title,
                boundary_confidence=(
                    BOUNDARY_CONFIDENCE_INFERRED
                    if title == UNTITLED
                    else BOUNDARY_CONFIDENCE_EXPLICIT
                ),
                continuity=(
                    CONTINUITY_CONTINUOUS
                    if run_counts[title] == 1
                    else CONTINUITY_DISCONTINUOUS
                ),
                paragraph_count=0,
            ))

        # Build chunks with proper start_char/end_char computation
        chunks: list[Chunk] = []
        start_char = 0
        for idx, (title, group_paras) in enumerate(runs):
            char_count = sum(len(p.text) for p in group_paras)
            meta = next(m for m in chapters if m.title == title)
            meta.paragraph_count += len(group_paras)
            chunks.append(Chunk(
                index=idx,
                title=title,
                start_char=start_char,
                end_char=start_char + char_count,
                char_count=char_count,
                source_md5=source_md5,
                chapter_id=chapter_ids[title],
                boundary_confidence=meta.boundary_confidence,
            ))
            start_char += char_count

        # Compute total characters
        total_chars = sum(len(p.text) for p in paragraphs)

        # Estimate chunks based on document-order chapter runs
        estimated_chunks = len(runs)

        # Build metadata
        metadata = DocumentMetadata(source_md5=source_md5)

        return ChunkedResult(
            chunks=chunks,
            total_chars=total_chars,
            estimated_chunks=estimated_chunks,
            metadata=metadata,
            chapters=chapters,
        )
