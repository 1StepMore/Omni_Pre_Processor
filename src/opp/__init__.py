"""OPP - Omni Pre-Processor: Document content extraction package."""

__version__ = "0.1.0"

from opp.extractors.docx import DOCXExtractor
from opp.extractors.pptx import PPTXExtractor
from opp.extractors.pdf import PDFExtractor
from opp.extractors.base import ExtractorBase
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    SlideData,
    TableData,
)

__all__ = [
    "DOCXExtractor",
    "PPTXExtractor",
    "PDFExtractor",
    "ExtractorBase",
    "MarkdownGenerator",
    "DocumentMetadata",
    "ExtractionResult",
    "ImageData",
    "ParagraphData",
    "SlideData",
    "TableData",
]