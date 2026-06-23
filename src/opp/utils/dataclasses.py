from pathlib import Path
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentMetadata:
    page_count: int | None = None
    file_size: int | None = None
    format_type: str | None = None
    source_md5: str | None = None
    # Email-specific fields
    subject: str | None = None
    sender: str | None = None
    to: str | None = None
    cc: str | None = None
    date: str | None = None


@dataclass
class RunData:
    """A text run with formatting properties."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_size: int | None = None  # half-points
    font_name: str | None = None
    color: str | None = None      # hex color like "FF0000"


@dataclass
class ParagraphData:
    text: str
    style: str | None = None
    level: int | None = None
    chapter: str | None = None
    page: int | None = None
    runs: list[RunData] = field(default_factory=list)
    position: int = 0  # Block position for ordering interleaved output
    para_index_in_body: int | None = None  # Absolute w:p index in body for XLIFF resname


@dataclass
class TableData:
    headers: list[str]
    rows: list[list[str]]
    position: int = 0  # Table index for ordering interleaved output


@dataclass
class ImageData:
    data: bytes = b""
    mime_type: str = ""
    width: int | None = None
    height: int | None = None

    # Position fields - only ONE of these has a value per ExtractionResult (format-specific)
    paragraph_index: int | None = None  # DOCX inline drawings (0-based, None for floating)
    page_number: int | None = None      # PDF pages (1-based)
    slide_index: int | None = None      # PPTX slides (0-based)
    element_index: int | None = None    # HTML DOM elements (0-based)
    spine_index: int | None = None      # EPUB spine order (0-based)
    is_floating: bool = False              # DOCX: True if <wp:anchor>, False if <wp:inline>

    # E2E-75: True when the extractor's markdown already contains the
    # ``![...](...)`` reference inline (e.g. HTML via markdownify).
    # ``MarkdownGenerator`` skips the generator's own inline injection
    # and the trailing ``## Images`` block to avoid double-embedding.
    is_inline_in_md: bool = False

    # Anchor coordinates (EMU = English Metric Units, 914400 EMU = 1 inch).
    # Only meaningful for floating DOCX images (is_floating=True). Phase 3
    # (ORF wp:anchor injection) reads these to rebuild <wp:positionH>/<wp:positionV>
    # on the regenerated DOCX. Default 0 keeps the field optional for inline images.
    wp_anchor_h: int = 0
    wp_anchor_v: int = 0

    # Temp path for large images streamed to disk instead of kept in data bytes.
    # When set, data is typically b"" and the bytes reside on disk at this path.
    # Pipeline uses this to skip redundant write-to-temp-file step.
    temp_path: Path | None = None


@dataclass
class AttachmentData:
    filename: str
    mime_type: str
    data: bytes


@dataclass
class SlideData:
    index: int
    shapes: list[ParagraphData]
    notes: str | None = None


@dataclass
class TextBlockData:
    text: str
    bbox: tuple
    page: int


@dataclass
class ExtractionResult:
    paragraphs: list[ParagraphData]
    tables: list[TableData]
    images: list[ImageData]
    attachments: list[AttachmentData] = field(default_factory=list)
    metadata: DocumentMetadata | None = None
    warnings: list[str] = field(default_factory=list)
    is_transcription: bool = False
    skeleton: bytes | None = None
    skeleton_files: list[str] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = DocumentMetadata()
        if self.warnings is None:
            self.warnings = []

    @property
    def content(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)
