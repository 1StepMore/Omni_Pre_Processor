from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentMetadata:
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    format_type: Optional[str] = None
    source_md5: Optional[str] = None
    # Email-specific fields
    subject: Optional[str] = None
    sender: Optional[str] = None
    to: Optional[str] = None
    cc: Optional[str] = None
    date: Optional[str] = None


@dataclass
class RunData:
    """A text run with formatting properties."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_size: Optional[int] = None  # half-points
    font_name: Optional[str] = None
    color: Optional[str] = None      # hex color like "FF0000"


@dataclass
class ParagraphData:
    text: str
    style: Optional[str] = None
    level: Optional[int] = None
    chapter: Optional[str] = None
    page: Optional[int] = None
    runs: List[RunData] = field(default_factory=list)
    position: int = 0  # Block position for ordering interleaved output
    para_index_in_body: Optional[int] = None  # Absolute w:p index in body for XLIFF resname


@dataclass
class TableData:
    headers: List[str]
    rows: List[List[str]]
    position: int = 0  # Table index for ordering interleaved output


@dataclass
class ImageData:
    data: bytes
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None

    # Position fields - only ONE of these has a value per ExtractionResult (format-specific)
    paragraph_index: Optional[int] = None  # DOCX inline drawings (0-based, None for floating)
    page_number: Optional[int] = None      # PDF pages (1-based)
    slide_index: Optional[int] = None      # PPTX slides (0-based)
    element_index: Optional[int] = None    # HTML DOM elements (0-based)
    spine_index: Optional[int] = None      # EPUB spine order (0-based)
    is_floating: bool = False              # DOCX: True if <wp:anchor>, False if <wp:inline>

    # Anchor coordinates (EMU = English Metric Units, 914400 EMU = 1 inch).
    # Only meaningful for floating DOCX images (is_floating=True). Phase 3
    # (ORF wp:anchor injection) reads these to rebuild <wp:positionH>/<wp:positionV>
    # on the regenerated DOCX. Default 0 keeps the field optional for inline images.
    wp_anchor_h: int = 0
    wp_anchor_v: int = 0


@dataclass
class AttachmentData:
    filename: str
    mime_type: str
    data: bytes


@dataclass
class SlideData:
    index: int
    shapes: List[ParagraphData]
    notes: Optional[str] = None


@dataclass
class TextBlockData:
    text: str
    bbox: tuple
    page: int


@dataclass
class ExtractionResult:
    paragraphs: List[ParagraphData]
    tables: List[TableData]
    images: List[ImageData]
    attachments: List[AttachmentData] = field(default_factory=list)
    metadata: Optional[DocumentMetadata] = None
    warnings: List[str] = field(default_factory=list)
    is_transcription: bool = False
    skeleton: Optional[bytes] = None
    skeleton_files: Optional[List[str]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = DocumentMetadata()
        if self.warnings is None:
            self.warnings = []

    @property
    def content(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)
