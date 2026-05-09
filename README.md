# OPP - Omni Pre-Processor

Document content extraction package for DOCX, PPTX, and PDF files.

## Phase 0 Status

**Current Focus**: Extractors only

This phase implements the core extraction classes:
- `ExtractorBase` - Abstract base class for all extractors
- `ExtractorResult` - Structured result container
- `DOCXExtractor` - Word document text/table extraction
- `PPTXExtractor` - PowerPoint text/shape extraction
- `PDFExtractor` - PDF text extraction

### What's Included

- Pure Python implementation
- Type hints throughout
- Structured output (not raw text)

### What's NOT Included (Future Phases)

- CLI interface
- Markdown generation
- OCR capabilities
- File format detection

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from opp import DOCXExtractor, ExtractorResult

extractor = DOCXExtractor()
result: ExtractorResult = extractor.extract("document.docx")
print(result.content)
```

## Development

```bash
pip install -e ".[dev]"

pytest

mypy src/
```