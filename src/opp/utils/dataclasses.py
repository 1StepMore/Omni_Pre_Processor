from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentMetadata:
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    format_type: Optional[str] = None
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
    runs: List[RunData] = field(default_factory=list)


@dataclass
class TableData:
    headers: List[str]
    rows: List[List[str]]


@dataclass
class ImageData:
    data: bytes
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None


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
