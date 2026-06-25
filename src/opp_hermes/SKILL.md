---
name: opp-hermes
description: OPP document extraction integration for Hermes agents. Use opp_extract tool for formats beyond Hermes built-in extractors (DOCX, PPTX, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images with OCR, Audio/Video transcription). OPP supplements Hermes built-in pymupdf and marker-pdf extractors.
---

# OPP Hermes Integration

Use the `opp_extract` tool when Hermes built-in extractors cannot handle the task.

## Mental Model

OPP supplements Hermes built-in extractors. Think of it as a specialized tool that handles formats the general-purpose extractors do not support.

```
Hermes built-in extractors: PDF (pymupdf, marker-pdf)
OPP: Everything else (DOCX, PPTX, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images, Audio/Video)
```

## When to Use OPP vs Built-in Extractors

| Format | Hermes Built-in | Use OPP |
|--------|-----------------|---------|
| PDF | Yes (pymupdf, marker-pdf) | No, unless PDF has complex structure |
| DOCX | No | Yes |
| PPTX | No | Yes |
| XLSX | No | Yes |
| CSV | No | Yes |
| JSON | No | Yes |
| XML | No | Yes |
| HTML | No | Yes |
| EPUB | No | Yes |
| EML | No | Yes |
| MSG | No | Yes |
| Images (OCR) | No | Yes |
| Audio/Video | No | Yes |
| YouTube URL | No | Yes |

## Decision Framework

Ask yourself: Is the file a PDF?
- **Yes** → Use Hermes built-in PDF extractor
- **No (DOCX, PPTX, XLSX, etc.)** → Use `opp_extract`

## Usage

### Extract DOCX content

```
opp_extract(file_path="/path/to/document.docx", output_formats=["md"])
```

### Generate XLIFF for translation

```
opp_extract(file_path="/path/to/doc.docx", output_formats=["xlf"], source_lang="en", target_lang="zh")
```

### Batch process mixed formats

```
opp_extract(file_path="/path/to/batch", output_formats=["md"])
```

### Image OCR

```
opp_extract(file_path="/path/to/scan.png", output_formats=["md"])
```

## Security

- **Allowlist required**: Set `OPP_MCP_ALLOWED_DIRS` environment variable
- **100MB file size limit**: Default maximum file size is 100MB
- **60s timeout**: Default extraction timeout is 60 seconds
- **Local files only**: No network file access

## Configuration

Hermes plugin configuration:

```yaml
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
    env:
      OPP_MCP_ALLOWED_DIRS: "/documents:/output"
      OPP_MCP_MAX_FILE_SIZE: "100000000"
      OPP_MCP_TIMEOUT: "60"
```

## Output Format

The `opp_extract` tool returns content in your chosen format:

- **markdown** (default) — text-only output. Use for documents where
  layout is not critical (web content, docs, e-books).
- **xliff** — XLIFF + skeleton.zip. Use when the original layout must
  be preserved end-to-end (contracts, branded docs). Pair with ORF
  `apply-xliff`.
- **both** — emit all three. Use when downstream choice is uncertain.

See [Pipeline Selection Strategy](https://github.com/1StepMore/Omni_Suite/blob/main/README.md#pipeline-selection-strategy)
for the full decision tree.

## Supported Formats

DOCX, PPTX, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images (OCR), Audio/Video transcription, YouTube URL