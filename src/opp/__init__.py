"""OPP - Omni Pre-Processor: Document content extraction package."""

<<<<<<< HEAD
__version__ = "0.7.5"
=======
__version__ = "0.7.4"
>>>>>>> 6804975 (feat(OPP#12): standardize MCP tool responses to {success, content?, error?: {code, message}})

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