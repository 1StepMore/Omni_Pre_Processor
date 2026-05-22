# OPP - Omni Pre-Processor

[![PyPI version](https://img.shields.io/pypi/v/opp.svg)](https://pypi.org/project/opp/)
[![Python versions](https://img.shields.io/pypi/pyversions/opp.svg)](https://pypi.org/project/opp/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/opp.svg)](https://pypi.org/project/opp/)

Document content extraction for DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and Image (OCR).

## Features

- **Multi-format extraction** - DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Image, IPYNB, YouTube URL
- **Image OCR** - Tesseract and RapidOCR with graceful fallback
- **Email extraction** - EML (RFC 822) and MSG (Outlook) with attachment recursion
- **Audio/Video transcription** - Whisper-based ASR
- **Format auto-detection** - Magic bytes detection (extension not required)
- **Resource management** - MD5 deduplication, UUID naming for images
- **Pipeline orchestrator** - detect → extract → manage → report
- **CLI interface** - Full command-line with batch support
- **Output formats** - Markdown and XLIFF 1.2/2.0
- **Manifest metadata** - JSON manifest with source info, extraction stats, and image data
- **Skeleton preservation** - Original DOCX/PPTX ZIP structure preserved for downstream XLIFF→DOCX/PPTX backfill

## Installation

```bash
# Core package
pip install -e .

# With office/data formats (XLSX, CSV, JSON, XML)
pip install -e ".[office]"

# With email and OCR (EML, MSG, Tesseract, RapidOCR)
pip install -e ".[email]"
```

## Quick Start

### Python API

```python
from opp import DOCXExtractor, PDFExtractor, PPTXExtractor
from opp.detector import detect_format
from opp.pipeline import OPPPipeline

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
# Extract to Markdown
opp --target-format=md document.docx

# Extract to XLIFF for translation
opp --target-format=xlf --source-lang=en --target-lang=zh document.docx

# Generate both MD and XLIFF
opp --target-format=both --source-lang=en --target-lang=zh document.docx

# Custom output directory
opp --target-format=md --output-dir ./output document.docx

# Image OCR
opp --ocr-engine tesseract scan.png

# Batch processing
opp --batch file1.docx file2.pdf file3.pptx
```

### Windows Batch Scripts

| Script | Description |
|--------|-------------|
| `md.bat` | Convert to Markdown |
| `en2cn_xliff.bat` | English source → Chinese XLIFF |
| `cn2en_xliff.bat` | Chinese source → English XLIFF |

```batch
md.bat "document.docx"
md.bat "folder"

en2cn_xliff.bat "english.docx"
cn2en_xliff.bat "中文.docx"
```

Supports drag-drop of files **and folders**. Logs saved to `logs/`.

### Output Files

Every extraction produces a `manifest.json` and optionally a `skeleton.zip`:

```
output_dir/
├── document.md              # Extracted Markdown
├── document.xlf             # Extracted XLIFF (translation-ready)
├── document_manifest.json   # Metadata about source and extraction
└── document.skeleton.zip    # Original DOCX/PPTX ZIP (for backfill)
```

#### manifest.json

Records source file info, extraction outputs, and resources:

```json
{
  "manifest_version": "1.0",
  "generated_at": "2026-05-22T14:30:00Z",
  "tool": "OPP",
  "tool_version": "0.2.0",
  "source": {
    "file_path": "/path/to/spec.docx",
    "original_filename": "spec.docx",
    "format": "DOCX",
    "file_size_bytes": 45824,
    "file_hash_md5": "a1b2c3d4e5f6..."
  },
  "extraction": {
    "source_lang": "en",
    "target_lang": "zh",
    "outputs": {
      "markdown": { "path": "spec.md", "paragraph_count": 150, "table_count": 3 },
      "xliff": { "path": "spec.xlf", "trans_unit_count": 42 }
    },
    "images": [
      { "mime_type": "image/png", "width": 800, "height": 600, "data_size_bytes": 24580 }
    ],
    "warnings": []
  },
  "resources": { "storage_dir": "resources", "image_count": 5 },
  "skeleton": {
    "path": "spec.skeleton.zip",
    "format": "ZIP",
    "key_files": ["word/document.xml", "word/styles.xml", "[Content_Types].xml"]
  }
}
```

#### skeleton.zip

Preserves the original OOXML ZIP structure for DOCX/PPTX files. This enables downstream ORF tools to perform XLIFF→DOCX/PPTX backfill by replacing content in the preserved skeleton.

| Format | Key Files Preserved |
|--------|---------------------|
| DOCX | `word/document.xml`, `word/styles.xml`, `word/numbering.xml`, `word/settings.xml`, `[Content_Types].xml` |
| PPTX | All files under `ppt/` prefix (slides, layouts, media)

## Project Structure

```
src/opp/
├── detector.py           # Format auto-detection
├── extractors/           # Document extractors
│   ├── docx.py
│   ├── pptx.py
│   ├── pdf.py
│   ├── xlsx.py
│   ├── csv.py
│   ├── json.py
│   ├── xml.py
│   ├── email.py
│   └── image_ocr.py
├── channels/             # Output formatters
│   ├── table_channel.py   # DataFrame → Markdown table
│   └── keyvalue_channel.py # dict → XLIFF
├── xliff/                # XLIFF 1.2/2.0 generator
├── pipeline.py           # OPPPipeline orchestrator
├── resource_manager.py   # Image deduplication
└── cli.py               # Command-line interface
```

## Architecture

```
                     ┌─────────────────────────────────────────┐
                     │              OPPPipeline                  │
                     │  detect_format() → Extractor → Report   │
                     └─────────────────────────────────────────┘

┌──────────┐    ┌───────────┐    ┌────────────────┐    ┌──────────────┐
│ detector │───▶│ extractors│───▶│resource_manager│───▶│error_handler │
│  magic   │    │  DOCX/...  │    │  MD5 + UUID    │    │ HTML/text    │
└──────────┘    └───────────┘    └────────────────┘    └──────────────┘
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=src/opp --cov-report=term-missing
```

## Test Coverage

| Module | Tests |
|--------|-------|
| detector | 13 |
| resource_manager | 18 |
| error_handler | 18 |
| integration | 25 |
| cli | 18 |
| e2e | 52 |
| xliff | 40+ |
| extractors | 140+ |
| manifest generation | 6 |
| skeleton preservation | 6 |
| **Total** | **491+** |

## Batch Testing

Test files available in `batch_test/` covering all formats.

```bash
opp --target-format=both --source-lang=en --target-lang=zh --output-dir=output batch_test/
```

## MCP Server (Agent-Facing)

The OPP MCP server provides document extraction capabilities to AI agents via the Model Context Protocol. AI assistants can use these tools to process documents without needing to understand OPP's internal architecture.

### Why Use the MCP Server?

- **Agent integration** - Connect OPP to any MCP-compatible AI assistant
- **stdio transport** - Communication over standard input/output for security
- **5 extraction tools** - Cover all major document formats
- **Path security** - Directory allowlist prevents unauthorized file access

### Installation

```bash
# Install OPP with MCP server support
pip install -e ".[mcp]"
```

### Quick Start

**Start the server manually:**
```bash
python -m opp.mcp.server
```

**Auto-start with uvx:**
```bash
uvx opp-mcp-server
```

**Auto-start with npx:**
```bash
npx opp-mcp-server
```

### Hermes Configuration

Add OPP to your Hermes agent configuration:

```yaml
agents:
  my-agent:
    tools:
      - name: opp
        type: code
        config:
          server_command: uvx opp-mcp-server
          allowed_directories:
            - /path/to/documents
            - /path/to/output
```

### Available Tools

| Tool | Description |
|------|-------------|
| `extract_document` | Extract content from a single document file. Supports DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and images. Returns markdown or structured content. |
| `batch_extract` | Process multiple files in one request. Takes an array of file paths and processes them sequentially. Returns extraction results for each file. |
| `detect_format` | Identify the file format of a document using magic bytes detection. Works regardless of file extension. Returns format name and confidence score. |
| `generate_markdown` | Convert a document to markdown format. Specify source and target languages for proper text processing. |
| `generate_xliff` | Convert a document to XLIFF format for translation workflows. Requires source-lang and target-lang parameters. |

### Security

The MCP server enforces path validation to prevent unauthorized file access.

**Allowlist configuration:**

```bash
# Via environment variable
export OPP_MCP_ALLOWED_DIRS="/allowed/documents,/allowed/output"

# Via configuration file
# Create opp_mcp_config.yaml with:
# security:
#   allowed_directories:
#     - /path/to/documents
#     - /path/to/output

**Configuration file** (`opp_mcp_config.yaml`):

```yaml
security:
  allowed_directories:
    - /mnt/d/贯维/Documents
    - /mnt/d/贯维/Output
    - ./documents

server:
  host: localhost
  port: 8765

extraction:
  default_target_format: md
  ocr_engine: tesseract
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPP_ALLOWED_DIRECTORIES` | Comma-separated list of allowed directories | Required |
| `OPP_RESOURCE_STORAGE_DIR` | Directory for extracted images | `./resources` |
| `OPP_OCR_ENGINE` | OCR engine to use | `tesseract` |
| `OPP_LOG_LEVEL` | Logging level | `INFO` |