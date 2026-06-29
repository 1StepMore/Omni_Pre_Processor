"""OPP - Omni Pre-Processor: Document content extraction package."""

try:
    from importlib.metadata import version as _v
    __version__ = _v("omni-pre-processor")
except Exception:  # expected — package metadata unavailable, hardcoded fallback
    __version__ = "0.9.1"

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
from opp.xliff import XLIFFFileGenerator, XLIFFValidator
from opp.xliff import XLIFFTransUnit, XLIFFFileAttributes, XLIFFUnitState

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
    "XLIFFFileGenerator",
    "XLIFFValidator",
    "XLIFFTransUnit",
    "XLIFFFileAttributes",
    "XLIFFUnitState",
]