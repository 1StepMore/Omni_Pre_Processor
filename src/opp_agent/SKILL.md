---
name: opp-extract
description: Extract content from documents (DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images with OCR, Audio/Video transcription, YouTube). Converts documents to markdown or XLIFF for translation workflows.
mcp:
  opp:
    command: uvx
    args: ["opp-mcp-server"]
    env:
      OPP_MCP_ALLOWED_DIRS: "${workspace_dir}"
      OPP_MCP_MAX_FILE_SIZE: "100000000"
---

# OPP Extract Skill

Use OPP when you need to extract content from documents.

## When to Use This Skill

- Extracting text from PDF, DOCX, PPTX files
- Converting documents to markdown for analysis
- Generating XLIFF files for translation
- OCR on scanned documents or images
- Transcribing audio/video to text
- Extracting tables from spreadsheets
- Processing email attachments recursively

## Tools Available

- `extract_document` - Main extraction tool
- `batch_extract` - Process multiple files
- `detect_format` - Identify file format
- `generate_markdown` - Generate markdown output
- `generate_xliff` - Generate XLIFF for translation

## Usage Examples

```
# Extract content from a document
extract_document(file_path="/path/to/document.docx", output_formats=["md"])

# Generate XLIFF for translation
extract_document(file_path="/path/to/doc.docx", output_formats=["xlf"], source_lang="en", target_lang="zh")

# Batch process multiple files
batch_extract(file_paths=["/path/to/doc1.docx", "/path/to/doc2.pdf"], output_formats=["md"])
```

## Security

- Only processes files within allowed directories
- File size limit: 100MB default
- No network access (local files only)
- Timeout: 60 seconds per extraction