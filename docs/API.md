# OPP API Reference

Complete reference for every command-line flag, every MCP tool, every error code, and every exit code exposed by the Omni Pre-Processor (OPP) package.

Package: `omni-pre-processor` (PyPI distribution) / `opp` (Python import)
Version: 0.6.1
Source: `Omni_Pre_Processor/src/opp/`
Console scripts: `opp`, `opp-mcp-server`

---

## Table of Contents

1. [CLI reference](#cli-reference)
2. [MCP tools reference](#mcp-tools-reference)
3. [Environment variables](#environment-variables)
4. [Output artifacts](#output-artifacts)
5. [Error codes](#error-codes)
6. [Exit codes](#exit-codes)
7. [Python API (selected)](#python-api-selected)

---

## CLI reference

The CLI is implemented in `src/opp/cli.py` using `argparse`. Run `opp --help` for inline docs.

### Synopsis

```bash
opp [OPTIONS] FILE [FILE ...]
```

`FILE` can be a single document, a list of documents, or a folder (auto-expanded recursively). Supported extensions: `.docx`, `.pptx`, `.pdf`, `.html`, `.epub`, `.eml`, `.msg`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`.

### All flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `files` | positional | (required) | One or more input files or folders. |
| `--detect-format` | bool | `False` | Auto-detect file format by magic bytes before processing. |
| `--resource-dir PATH` | path | (CWD/resources) | Directory for extracted images and resources. |
| `--report {html,text}` | choice | (none) | Generate error/processing report after run. |
| `--batch` | bool | `False` | Enable explicit batch processing mode. |
| `-o, --output PATH` | path | (none) | Output file for the report (used with `--report`). |
| `--target-format {md,xlf,both}` | choice | (none) | Output format(s) to generate. |
| `--source-lang CODE` | string | `zh` | Source language code (XLIFF: identifies source). |
| `--target-lang CODE` | string | (required for xlf/both) | Target language code. Falls back to `en` for `md`-only. |
| `--style-map JSON` | string | (none) | `'{"a5":1,"a6":2}'` — map DOCX/PPTX style names to heading levels. |
| `--no-embed-images` | bool | `False` | Write images as separate files (default: base64 inline). |
| `--output-dir PATH` | path | (input parent) | Output directory for generated files. |
| `-v, --verbose` | bool | `False` | Enable verbose logging. |
| `--ocr-engine {tesseract,rapidocr}` | choice | (none) | OCR engine for image files. |
| `--ocr-lang CODE` | string | (none) | Tesseract language code (`eng`, `chi_sim`, ...). |
| `--asr-engine {whisper}` | choice | (none) | ASR engine for audio files. |
| `--model-size {tiny,base,small,medium,large-v3}` | choice | `tiny` | Whisper model size. |
| `--config PATH` | path | (none) | Path to `opp_config.yaml`. |
| `--no-cache` | bool | `False` | Skip the `~/.omni_cache/opp/` cache check. |
| `--clear-cache` | bool | `False` | Remove all cached OPP outputs and exit immediately. |
| `--max-file-size MB` | int | `0` (unlimited) | Reject files larger than this size in MB. |

### Examples

```bash
# Markdown extraction (default: source-lang=zh, target-lang=en)
opp --target-format=md document.docx

# XLIFF for translation pipeline
opp --target-format=xlf --source-lang=en --target-lang=zh document.docx

# Both MD + XLIFF in one run
opp --target-format=both --source-lang=en --target-lang=zh document.docx

# Auto-detect format and report
opp --detect-format --report=html -o report.html document.docx

# OCR a scanned image
opp --ocr-engine=tesseract --ocr-lang=eng scan.png

# Batch process a folder
opp --target-format=both --output-dir=./out ./batch_test/

# Force re-extraction (bypass cache)
opp --no-cache --target-format=xlf --target-lang=fr file.epub

# Clear the global OPP cache
opp --clear-cache
```

---

## MCP tools reference

The MCP server is `opp.mcp.server` (entry point: `opp-mcp-server`). It uses `mcp.server.Server` + `mcp.server.stdio.stdio_server` (stdin/stdout transport). All 7 tool functions are also importable as module-level async functions for direct in-process tests.

Security layers: token-bucket rate limiter, optional `MCP_SHARED_SECRET` auth, `PathValidator` (allowlist + extension whitelist + size + symlink checks).

All tool responses are JSON-encoded `dict`s returned as a single `TextContent` block.

### 1. `extract_document`

Extract content from a single document. Returns Markdown and/or XLIFF as text in the response (NOT written to disk by default).

**Input schema**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Absolute path to the source document. |
| `output_formats` | string \| string[] | no | `["md"]` | One or more of `md`, `xlf`, `both`. |
| `source_lang` | string | no | `zh` | Source language code. |
| `target_lang` | string | no | `en` | Target language code. |
| `resource_dir` | string | no | (none) | Directory for extracted resources. Must be inside an allowed directory. |
| `auth_token` | string | no | (none) | Shared secret (only required if `MCP_SHARED_SECRET` is set). |

**Output schema (success)**

```json
{
  "success": true,
  "format": "docx",
  "extraction": { "paragraphs": 150, "tables": 3, "images": 5, "warnings": [] },
  "md_content": "---\nsource_lang: zh\ntarget_lang: en\n---\n\n# Title\n...",
  "xliff_content": "<?xml version=\"1.0\"?>\n<xliff ...>...</xliff>",
  "xliff_units_count": 42,
  "images_dir": "/path/to/document_images",
  "request_id": "uuid",
  "warnings": []
}
```

**Example call**

```json
{
  "tool": "extract_document",
  "params": {
    "file_path": "/data/contracts/lease.docx",
    "output_formats": "both",
    "source_lang": "en",
    "target_lang": "zh"
  }
}
```

**Persisting output** — the MCP response is text-only. The caller (agent or test) must write the text to disk if persistence is required.

---

### 2. `batch_extract`

Process multiple files in one request. Each file is validated and processed sequentially.

**Input schema**

| Param | Type | Required | Default |
|-------|------|----------|---------|
| `file_paths` | string[] | yes | — |
| `output_formats` | string \| string[] | no | `["md"]` |
| `source_lang` | string | no | `zh` |
| `target_lang` | string | no | `en` |
| `auth_token` | string | no | (none) |

**Output schema**

```json
{
  "success": true,
  "results": [
    {
      "file_path": "/data/a.docx",
      "success": true,
      "format": "docx",
      "md_content": "...",
      "xliff_content": "...",
      "xliff_units_count": 23
    }
  ],
  "successful": 1,
  "failed": 0,
  "total_duration_ms": 1234.5
}
```

If any file fails path validation up-front, the whole call returns `success: false` with a `validation_errors` array and `results: []`. Per-file failures during processing populate individual error entries but the call still returns `success: true` overall.

---

### 3. `detect_format_tool`

Magic-bytes file format detection (extension-agnostic).

**Input schema**

| Param | Type | Required |
|-------|------|----------|
| `file_path` | string | yes |
| `auth_token` | string | no |

**Output**

```json
{ "success": true, "format": "docx", "confidence": 1.0 }
```

`format` is one of: `docx`, `pptx`, `pdf`, `xlsx`, `csv`, `json`, `xml`, `html`, `epub`, `email`, `image`, `audio`, `video`, `ipynb`, `youtube`, `unknown`.

---

### 4. `generate_xliff`

Extract to XLIFF only. Returns the XLIFF text and writes to `output_path` (default: `<input_stem>_generated.xlf` next to the input).

**Input schema**

| Param | Type | Required | Default |
|-------|------|----------|---------|
| `file_path` | string | yes | — |
| `source_lang` | string | no | `zh` |
| `target_lang` | string | no | `en` |
| `output_path` | string | no | `<stem>_generated.xlf` |
| `auth_token` | string | no | (none) |

**Output**

```json
{
  "success": true,
  "xliff_content": "<?xml ...",
  "output_path": "/data/lease_generated.xlf",
  "units_count": 42,
  "error": null
}
```

PDF inputs to XLIFF are blocked by design (unsupported by downstream tools) and return a `ValueError`-derived error.

---

### 5. `generate_markdown`

Extract to Markdown only. Returns MD text and writes to `output_path` (default: `<stem>_generated.md`).

**Input schema**

| Param | Type | Required | Default |
|-------|------|----------|---------|
| `file_path` | string | yes | — |
| `output_path` | string | no | `<stem>_generated.md` |
| `style_mapping` | object<string,int> | no | (none) |
| `embed_images` | bool | no | `true` |
| `auth_token` | string | no | (none) |

**Output**

```json
{
  "success": true,
  "markdown_content": "# Title\n...",
  "output_path": "/data/lease_generated.md",
  "images_dir": "/data/lease_generated_images",
  "images_count": 5
}
```

---

### 6. `save_skeleton`

Save the original DOCX/PPTX ZIP skeleton (required by ORF `apply_xliff` for XLIFF→DOCX/PPTX backfill).

**Input schema**

| Param | Type | Required | Default |
|-------|------|----------|---------|
| `file_path` | string | yes | — |
| `base_name` | string | no | `document` |
| `output_dir` | string | no | (input's parent) |
| `auth_token` | string | no | (none) |

**Output**

```json
{
  "success": true,
  "skeleton_path": "/data/document.skeleton.zip",
  "error": null
}
```

Key files preserved in the skeleton:
- DOCX: `word/document.xml`, `word/styles.xml`, `word/numbering.xml`, `word/settings.xml`, `[Content_Types].xml`
- PPTX: everything under `ppt/` (slides, layouts, media)

---

### 7. `ping`

Health check. Unauthenticated (no `@mcp_error_boundary`), but still subject to the rate limiter and shared-secret check.

**Input schema**

| Param | Type | Required |
|-------|------|----------|
| `auth_token` | string | no |

**Output**

```json
{ "success": true }
```

---

## Environment variables

| Variable | Applies to | Purpose | Default |
|----------|-----------|---------|---------|
| `OPP_MCP_ALLOWED_DIRS` | MCP | Colon/semicolon-separated allowlist of directories the MCP can read. | (none — no dirs allowed) |
| `OPP_MCP_MAX_FILE_SIZE` | MCP | Max input file size in bytes. | `100_000_000` (100MB) |
| `OPP_MCP_TIMEOUT` | MCP | Per-tool request timeout in seconds. | `60` |
| `OPP_MCP_HOST` | MCP | Bind host (informational, stdio transport). | `127.0.0.1` |
| `OPP_MCP_PORT` | MCP | Bind port (informational, stdio transport). | `8766` |
| `OPP_ALLOWED_DIRECTORIES` | CLI | Comma-separated allowlist for `--resource-dir`. | (CWD + /tmp) |
| `OMNI_CACHE_DIR` | CLI | Override the OPP cache root. | `~/.omni_cache/` |
| `OPP_OCR_ENGINE` | CLI | `tesseract` or `rapidocr` (set by `--ocr-engine`). | (auto) |
| `OPP_OCR_LANG` | CLI | Tesseract language. | `eng` |
| `OPP_ASR_ENGINE` | CLI | `whisper`. | (auto) |
| `OPP_MODEL_SIZE` | CLI | Whisper model size. | `tiny` |
| `MCP_SHARED_SECRET` | MCP | If set, every tool call must pass `auth_token=<secret>`. | (disabled) |
| `OMNI_TEST_FAKE_LLM` | All | Set by the Omni test suite to bypass LLM seams. | (off) |

> **MCP critical note** — the env var is `OPP_MCP_ALLOWED_DIRS`, NOT `OPP_ALLOWED_DIRECTORIES`. Setting the wrong name silently results in an empty allowlist and every tool call returns `OPP_PATH_DENIED`.

---

## Output artifacts

A successful CLI run with `--target-format=both` writes:

```
<output_dir>/
├── <stem>.md                  # Markdown with YAML frontmatter
├── <stem>.xlf                 # XLIFF 1.2 with <bx>/<ex> inline tags
├── <stem>_manifest.json       # Source + extraction metadata
├── <stem>_images.json         # (if images) Image positions and floating metadata
├── <stem>_images/             # (if images, only when --no-embed-images)
└── <stem>.skeleton.zip        # (DOCX/PPTX only) Original ZIP for ORF backfill
```

`manifest.json` top-level keys: `manifest_version`, `request_id`, `generated_at`, `tool`, `tool_version`, `source`, `extraction`, `resources`, `skeleton` (if any).

---

## Error codes

Returned in tool responses as `error_code` (and sometimes mirrored in `message`/`error` for back-compat).

| Code | Source | Meaning |
|------|--------|---------|
| `OPP_UNKNOWN_TOOL` | dispatcher | The tool name is not registered. |
| `OPP_INTERNAL_ERROR` | error boundary | Uncaught exception; check server logs. |
| `OPP_FILE_NOT_FOUND` | error boundary | A required file does not exist. |
| `OPP_PERMISSION_DENIED` | error boundary | Filesystem permission error. |
| `OPP_INVALID_INPUT` | error boundary | ValueError — bad parameter or unsupported format. |
| `OPP_MISSING_KEY` | error boundary | A required dict key was missing. |
| `OPP_TIMEOUT` | error boundary | Operation exceeded time limit. |
| `OPP_NOT_IMPLEMENTED` | error boundary | Feature is not yet implemented. |
| `OPP_PATH_DENIED` | error boundary | Path failed allowlist/extension/symlink check. |
| `OPP_RESOURCE_EXHAUSTED` | error boundary | Memory or image-count limit hit. |
| `AUTH_FAILED` | auth | `MCP_SHARED_SECRET` mismatch. |
| `RATE_LIMITED` | rate limiter | Token bucket exhausted. |

CLI exit messages use human strings; the above codes only appear in MCP responses.

---

## Exit codes

| Code | Meaning | Trigger |
|------|---------|---------|
| `0` | Success | All files processed, `stats["errors"] == 0`. |
| `1` | Partial or total failure | `stats["errors"] > 0`, unknown format, or no supported files found. |
| `1` | Uncaught exception | Any exception escaping `main()` triggers `sys.exit(1)` in the `__main__` block. |

`--clear-cache` is the only CLI flag that exits 0 without doing extraction work (cache count is reported in the log).

---

## Python API (selected)

The full surface lives in `src/opp/__init__.py` and the `extractors/` package. Selected high-value entry points:

```python
from opp import DOCXExtractor, PDFExtractor, PPTXExtractor, MarkdownGenerator
from opp.detector import detect_format, FormatType
from opp.pipeline import OPPPipeline

# Direct extractor
ext = DOCXExtractor()
result = ext.extract("contract.docx")
print(result.content)

# Auto-detect
fmt, confidence = detect_format("mystery_file")
print(fmt.value, confidence)

# Full pipeline (detect → extract → manage resources → report)
pipeline = OPPPipeline(resource_storage_dir="./resources")
result = pipeline.process_file("contract.docx")
print(result.content, result.images_stored)
```

Dataclasses: `ExtractionResult`, `DocumentMetadata`, `ImageData`, `ParagraphData`, `SlideData`, `TableData` — all in `opp.utils.dataclasses`.

XLIFF: `XLIFFFileGenerator`, `XLIFFValidator`, `XLIFFTransUnit`, `XLIFFFileAttributes`, `XLIFFUnitState` — in `opp.xliff`.
