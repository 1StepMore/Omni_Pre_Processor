# OPP - Omni Pre-Processor

Document content extraction package for DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and Image (OCR) files.

## Features

- **Multi-format extraction** - DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Image support
- **Image OCR** - Tesseract and RapidOCR engines with graceful fallback
- **Email extraction** - EML (RFC 822) and MSG (Outlook) with attachment recursion
- **Format auto-detection** - Magic bytes detection (no file extension required)
- **Resource management** - MD5 deduplication, UUID naming for images
- **Error handling** - Unified error hierarchy with HTML/text reports
- **Pipeline orchestrator** - Single API for detect → extract → manage → report
- **CLI interface** - Full command-line interface with batch support
- **Output generation** - Markdown and XLIFF export for localization pipelines

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Core extractors (DOCX/PPTX/PDF) |
| Phase 1 | ✅ Complete | Markdown generation |
| Phase 2 | ✅ Complete | XLIFF 1.2/2.0 export |
| Phase 3 | ✅ Complete | Multi-format convergence, auto-detection, resource management |
| Phase 4 | ✅ Complete | CLI/Pipeline integration, E2E tests, PyPI publishing |
| Phase 5 | ✅ Complete | Office & data formats (XLSX/CSV/JSON/XML) |
| Phase 6 | ✅ Complete | Web & ebook formats (HTML/EPUB) |
| Phase 7 | ✅ Complete | Email & image OCR (EML/MSG/Image) |

## Installation

```bash
# Core package
pip install -e .

# With office/data format support (XLSX, CSV, JSON, XML)
pip install -e ".[office]"

# With email and image OCR support (EML, MSG, Tesseract, RapidOCR)
pip install -e ".[email]"
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

# Generate Markdown output
opp --target-format=md document.docx

# Generate XLIFF for translation
opp --target-format=xlf --source-lang=en --target-lang=zh document.docx

# Generate both MD and XLIFF
opp --target-format=both --source-lang=en --target-lang=zh document.docx

# Custom output directory
opp --target-format=md --output-dir ./output document.docx

# Image OCR with Tesseract (default)
opp --ocr-engine tesseract scan.png

# Image OCR with RapidOCR
opp --ocr-engine rapidocr scan.png

# Image OCR with specific language
opp --ocr-engine tesseract --ocr-lang chi_sim scan.png

# Email extraction with attachments
opp --target-format=both email.msg
```

### Batch Entry Points (Windows)

| Script | Purpose | Usage |
|--------|---------|-------|
| `md.bat` | Convert to Markdown | `md.bat "file.docx"` or `md.bat "folder"` |
| `xliff.bat` | Convert to XLIFF | `xliff.bat "file.docx" [target-lang]` |

Supports drag-drop of files **and folders**. Logs saved to `logs/` directory.

```batch
# Convert single file to Markdown
md.bat "document.docx"

# Convert folder to Markdown (batch mode)
md.bat "folder" --output-dir ./output

# Convert to XLIFF for translation
xliff.bat "document.docx" zh
xliff.bat "folder" ja

# Verbose logging
md.bat "file.pdf" -v
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
│   ├── pdf.py
│   ├── xlsx.py          # Phase 5 - XLSX extractor
│   ├── csv.py            # Phase 5 - CSV extractor
│   ├── json.py           # Phase 5 - JSON extractor
│   ├── xml.py            # Phase 5 - XML extractor
│   ├── email.py          # Phase 7 - Email extractor (EML/MSG)
│   └── image_ocr.py      # Phase 7 - Image OCR extractor
├── channels/            # Phase 5 - Output channels
│   ├── table_channel.py   # DataFrame → Markdown table
│   └── keyvalue_channel.py # dict → XLIFF trans-unit
└── xliff/               # Phase 2 - XLIFF export
    ├── generator.py
    ├── validator.py
    └── xliff_dataclasses.py
```

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                        OPPPipeline                           │
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
| cli | 18 |
| e2e (docx/pptx/pdf) | 52 |
| opp-ol integration | 16 |
| xliff | 40+ |
| Phase 5 extractors (xlsx/csv/json/xml) | 100+ |
| Phase 5 channels | 20+ |
| Phase 7 extractors (email/image_ocr) | 15+ |
| **Total** | **472+** |

## PyPI Publishing

```bash
# Tag a release
git tag v0.1.1
git push origin v0.1.1

# GitHub Actions automatically:
# 1. Runs tests
# 2. Builds package
# 3. Publishes to TestPyPI for verification
# 4. On manual approval, publishes to PyPI
```
