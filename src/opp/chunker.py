from dataclasses import dataclass
from typing import List, Optional

from opp.utils.dataclasses import DocumentMetadata, ParagraphData


@dataclass
class Chunk:
    """Represents a chunk of text with its metadata."""
    index: int
    title: str | None
    start_char: int
    end_char: int
    char_count: int
    source_md5: str


@dataclass
class ChunkedResult:
    """Result of chunking operation with metadata."""
    chunks: list[Chunk]
    total_chars: int
    estimated_chunks: int
    metadata: DocumentMetadata


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
            ChunkedResult with chunks grouped by chapter and computed metadata
            
        Note:
            This method does NOT implement splitting logic.
            It only groups paragraphs by chapter and computes metadata.
            Actual chunk boundary determination is done by Pipeline/OLL.
        """
        # Group paragraphs by chapter
        chapter_groups: dict[str, list[ParagraphData]] = {}
        for p in paragraphs:
            chapter = p.chapter if p.chapter else "Untitled"
            if chapter not in chapter_groups:
                chapter_groups[chapter] = []
            chapter_groups[chapter].append(p)
        
        # Build chunks with proper start_char/end_char computation
        chunks = []
        start_char = 0
        for idx, (chapter_title, group_paras) in enumerate(chapter_groups.items()):
            char_count = sum(len(p.text) for p in group_paras)
            chunks.append(Chunk(
                index=idx,
                title=group_paras[0].chapter if group_paras[0].chapter else chapter_title,
                start_char=start_char,
                end_char=start_char + char_count,
                char_count=char_count,
                source_md5=source_md5
            ))
            start_char += char_count
        
        # Compute total characters
        total_chars = sum(len(p.text) for p in paragraphs)
        
        # Estimate chunks based on chapter count
        estimated_chunks = len(chapter_groups)
        
        # Build metadata
        metadata = DocumentMetadata(source_md5=source_md5)
        
        return ChunkedResult(
            chunks=chunks,
            total_chars=total_chars,
            estimated_chunks=estimated_chunks,
            metadata=metadata
        )
