# OPP - Omni Pre-Processor

Document content extraction package for DOCX, PPTX, and PDF files.

## Features

- **Multi-format extraction** - DOCX, PPTX, PDF support
- **Format auto-detection** - Magic bytes detection (no file extension required)
- **Resource management** - MD5 deduplication, UUID naming for images
- **Error handling** - Unified error hierarchy with HTML/text reports
- **Pipeline orchestrator** - Single API for detect → extract → manage → report
- **CLI interface** - Full command-line interface with batch support

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Core extractors (DOCX/PPTX/PDF) |
| Phase 1 | ✅ Complete | Markdown generation |
| Phase 2 | ✅ Complete | XLIFF 1.2/2.0 export |
| Phase 3 | ✅ Complete | Multi-format convergence, auto-detection, resource management |

## Installation

```bash
pip install -e .
```

## Quick Start

### Python API

```python
from opp import DOCXExtractor, PDFExtractor, PPTXExtractor
from opp.detector import detect_format, FormatType
from opp.pipeline import OPPPipeline
from opp.resource_manager import ResourceManager
from opp.error_handler import ErrorHandler

# Direct extraction
extractor = DOCXExtractor()
result = extractor.extract("document.docx")
print(result.content)

# Auto-detection
fmt, confidence = detect_format("document.docx")
print(f"Format: {fmt.value}, Confidence: {confidence}")

# Full pipeline
pipeline = OPPPipeline(resource_storage_dir="./resources")
result = pipeline.process_file("document.docx")
print(f"Extracted: {len(result.content)} chars, {result.images_stored} images")
```

### CLI

```bash
# Auto-detect format and extract
opp --detect-format document.docx

# Extract with resources to specific directory
opp --resource-dir ./output document.docx

# Generate HTML report
opp --report html document.docx -o report.html

# Batch processing
opp --batch file1.docx file2.pdf file3.pptx

# Full pipeline with all features
opp --detect-format --resource-dir ./images --report html --batch *.docx *.pdf *.pptx
```

## Development

```bash
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest tests/ -v --cov=src/opp --cov-report=term-missing
```

## Project Structure

```
src/opp/
├── detector.py          # Format auto-detection via magic bytes
├── resource_manager.py  # Image deduplication and UUID naming
├── error_handler.py     # Error hierarchy and HTML/text reports
├── pipeline.py          # OPPPipeline orchestrator
├── cli.py               # Command-line interface
├── markdown.py          # Markdown generation
├── extractors/          # Phase 0 - Document extractors
│   ├── base.py
│   ├── docx.py
│   ├── pptx.py
│   └── pdf.py
└── xliff/               # Phase 2 - XLIFF export
    ├── generator.py
    ├── validator.py
    └── xliff_dataclasses.py
```

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                        OPPPipeline                       │
                    │  detect_format() → Extractor → ResourceManager → Report    │
                    └─────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  detector.py │───▶│  extractors │───▶│ resource_manager │───▶│  error_handler  │
│  FormatType │    │  DOCX/PPTX/  │    │  MD5 dedup +     │    │  HTML/text       │
│  Magic bytes │    │  PDF         │    │  UUID naming     │    │  reports         │
└─────────────┘    └─────────────┘    └──────────────────┘    └──────────────────┘
```

## Test Coverage

| Module | Tests |
|--------|-------|
| detector | 13 |
| resource_manager | 18 |
| error_handler | 18 |
| integration | 21 |
| **Total** | **70+** |