# OPP - Omni Pre-Processor

[![PyPI version](https://img.shields.io/pypi/v/opp.svg)](https://pypi.org/project/opp/)
[![Python versions](https://img.shields.io/pypi/pyversions/opp.svg)](https://pypi.org/project/opp/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/opp.svg)](https://pypi.org/project/opp/)

Document content extraction for DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and Image (OCR).

## Features

- **Multi-format extraction** - DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Image, IPYNB, YouTube URL
- **Inline formatting tracking** - Bold, italic, underline, strikethrough preserved in XLIFF as `<bx>`/`<ex>` tags for downstream formatting restoration
- **Image OCR** - Tesseract and RapidOCR with graceful fallback
- **Email extraction** - EML (RFC 822) and MSG (Outlook) with attachment recursion
- **Audio/Video transcription** - Whisper-based ASR
- **Format auto-detection** - Magic bytes detection (extension not required)
- **Resource management** - MD5 deduplication, UUID naming for images
- **Floating image extraction** - Distinguishes `wp:anchor` (floating) from `wp:inline` drawings and carries `wp:positionH`/`wp:positionV` offsets in EMU units through `images.json` for downstream ORF reinjection
- **Pipeline orchestrator** - detect → extract → manage → report
- **CLI interface** - Full command-line with batch support
- **Output formats** - Markdown and XLIFF 1.2/2.0
- **Manifest metadata** - JSON manifest with source info, extraction stats, and image data
- **Skeleton preservation** - Original DOCX/PPTX ZIP structure preserved for downstream XLIFF→DOCX/PPTX backfill

## Prerequisites

- **Python >= 3.13** — required by all Omni Suite components (OPP, OL, ORF).
  Verify with `python3 --version`.

## Installation

```bash
# Core package
pip install -e .

# With office/data formats (XLSX, CSV, JSON, XML)
pip install -e ".[office]"

# With email and OCR (EML, MSG, Tesseract, RapidOCR)
pip install -e ".[email]"
```

### 可选依赖

除 `office`、`email` 外，以下可选依赖组支持特定输入格式：

| 依赖组 | 命令 | 用途 | 体积 |
|--------|------|------|------|
| `[ocr]` | `pip install -e ".[ocr]"` | 图片 OCR（RapidOCR） | ~100MB |
| `[youtube]` | `pip install -e ".[youtube]"` | YouTube `.url` 自动检测 | ~50MB |
| `[audio]` | `pip install -e ".[audio]"` | 音频转录（Whisper） | ~2GB |

- PDF 输入生成 XLIFF 已被正确拦截——此前 `format_type == "PDF"` 因大小写匹配错误从未生效，现已修复为 `"pdf"`。
- `.url` 文件现在被自动检测为 YouTube 源（读取首行 URL 并匹配 YouTube 域名）。

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

> **Note:** Windows `.bat` helper scripts are no longer provided. Use the CLI directly — see examples above.

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
| inline formatting | 53 |
| manifest generation | 6 |
| skeleton preservation | 6 |
| **Total** | **544+** |

## Batch Testing

Test files available in `batch_test/` covering all formats.

```bash
opp --target-format=both --source-lang=en --target-lang=zh --output-dir=output batch_test/
```

## Pipeline — Omni Localization Suite

OPP is **Step 1** of the Omni Localization Suite pipeline:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     OMNI LOCALIZATION SUITE                             │
│                                                                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│  │     OPP     │───▶│     OL      │───▶│     ORF      │               │
│  │  (提取)     │    │   (翻译)    │    │   (回写)    │               │
│  └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                        │
│  Step 1: OPP        Step 2: OL            Step 3: ORF                  │
│  Extract →          Translate →           Backfill →                  │
│  MD + XLIFF +       MD + XLIFF            DOCX/PPTX                   │
│  skeleton.zip                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

### Complete Workflow

```bash
# Step 1: OPP - Extract document to MD/XLIFF + skeleton.zip
opp --target-format=both --source-lang=en --target-lang=zh document.docx
# Output: document.md, document.xlf, document_manifest.json, document.skeleton.zip

# Step 2: OL - Translate to target language
ol translate-md document.md -s en -t zh -o translated/

# Step 3: ORF - Backfill translated content to target format
orf apply-xliff document.docx --xliff translated/document.xlf --output result.docx
```

## Related Projects

- [OL (Omni-Localizer)](https://github.com/1StepMore/Omni_Localizer) - **NEXT STEP** after OPP. Translates MD/XLIFF produced by OPP.
- [ORF (Omni-Re-Formatter)](https://github.com/1StepMore/Omni_Re_Formatter) - Backfills translated content to DOCX/PPTX/EPUB.

## For AI Agents

OPP outputs standardized artifacts for downstream processing:

| Artifact | Description | Used By |
|----------|-------------|---------|
| `{name}.md` | Markdown with YAML frontmatter (`source_lang`, `target_lang`) | OL (translate-md) |
| `{name}.xlf` | XLIFF 1.2/2.0 with `<bx>`/`<ex>` inline tags | OL (translate-xliff) |
| `{name}_manifest.json` | Metadata: source info, output paths, resources | ORF (manifest parser) |
| `{name}.skeleton.zip` | Original DOCX/PPTX ZIP structure | ORF (XLIFF→DOCX backfill) |

**MCP Tools Available:** `extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`, `ping`

### Floating Image Metadata

For DOCX inputs that contain anchored (floating) images, OPP emits an `is_floating: true` flag alongside `wp_anchor_h` and `wp_anchor_v` fields in `images.json` — both expressed in EMU (English Metric Units, 914400 EMU = 1 inch). The `paragraph_index` for floating drawings is `None` because they are not anchored to a `w:p` element. ORF consumes these fields to reinject `<wp:anchor>` blocks with `<wp:positionH>`/`<wp:positionV>` when backfilling the translated DOCX, preserving the original page layout. Inline images keep the previous JSON shape (no `is_floating` key) so downstream consumers that don't care about floating layout remain unaffected.

## MCP Server (Agent-Facing)

The OPP MCP server provides document extraction capabilities to AI agents via the Model Context Protocol. AI assistants can use these tools to process documents without needing to understand OPP's internal architecture.

### Why Use the MCP Server?

- **Agent integration** - Connect OPP to any MCP-compatible AI assistant
- **stdio transport** - Communication over standard input/output for security
- **7 extraction tools** - Cover all major document formats
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
| `save_skeleton` | Save the skeleton ZIP for an extracted document, preserving original OOXML structure (required by ORF `apply-xliff`). |
| `ping` | Health check endpoint. Returns server version and status. |

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
    - <your-documents-dir>
    - <your-output-dir>
    - ./documents

server:
  host: localhost
  port: 8765

extraction:
  default_target_format: md
  ocr_engine: tesseract
```

### Environment Variables

| Variable | Scope | Description | Default |
|----------|-------|-------------|---------|
| `OPP_MCP_ALLOWED_DIRS` | **MCP** | Colon/semicolon-separated allowlist of directories the MCP server can read (e.g. `/docs:/tmp/out`). **Required** for any `opp mcp` tool call to succeed. | (none) |
| `OPP_ALLOWED_DIRECTORIES` | CLI only | Comma-separated allowlist for the CLI's `--resource-dir` guard (`src/opp/cli.py:496`). NOT read by the MCP server. | (none) |
| `OPP_MCP_MAX_FILE_SIZE` | MCP | Max input file size in bytes | `104857600` (100 MB) |
| `OPP_MCP_TIMEOUT` | MCP | Per-tool request timeout in seconds | `300` |
| `OPP_MCP_HOST` | MCP | Bind host | `127.0.0.1` |
| `OPP_MCP_PORT` | MCP | Bind port | `8766` |
| `OMNI_METRICS_DIR` | MCP | Prometheus metrics directory | `/tmp/omni-metrics` |
| `MCP_SHARED_SECRET` | MCP | Shared-secret auth (Phase A4) | (none — auth disabled) |
| `OPP_RESOURCE_STORAGE_DIR` | CLI | Directory for extracted images | `./resources` |
| `OPP_OCR_ENGINE` | CLI | OCR engine | `tesseract` |
| `OPP_OCR_LANG` | CLI | OCR language | `eng` |
| `OPP_LOG_LEVEL` | CLI | Log level | `INFO` |
| `OMNI_LOG_FORMAT` | CLI/MCP | `console` (default) or `json` | `console` |
| `OMNI_TEST_FAKE_LLM=1` | CLI | Mock LLM responses (hermetic testing) | unset |