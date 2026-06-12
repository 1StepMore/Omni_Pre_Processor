# Integrating OPP with Hermes via MCP

This guide walks through configuring Hermes to use OPP (Omni Pre-Processor) as an MCP server for document extraction.

## Prerequisites

- Hermes agent installed and configured
- OPP installed with MCP support
- At least one directory containing documents to process

## Installation

Install OPP with the MCP optional dependency:

```bash
pip install -e ".[mcp]"
```

This installs the `opp-mcp-server` command and the `mcp` package dependency.

## Configuration

### Step 1: Create an Allowed Directories List

OPP enforces a security allowlist. Only files within these directories can be accessed. Decide which directories your agent needs to read from.

Example directories:
- `<your-documents-dir>` - Source documents
- `<your-output-dir>` - Where output files go

### Step 2: Configure Hermes

Add OPP to your Hermes configuration file. The exact location depends on your Hermes setup, but typically it's `hermes.yaml` or `config/hermes.yaml`.

```yaml
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
    env:
      OPP_MCP_ALLOWED_DIRS: "<your-documents-dir>:<your-output-dir>"
```

On Windows, use semicolons for the path separator:

```yaml
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
    env:
      OPP_MCP_ALLOWED_DIRS: "C:\Users\you\Documents;C:\Users\you\Output"
```

### Step 3: Alternative - YAML Config File

You can also create a dedicated OPP MCP config file:

```yaml
allowed_directories:
  - <your-documents-dir>
  - <your-output-dir>
  - ./documents

max_file_size_bytes: 104857600
request_timeout_seconds: 60
resource_storage_dir: ./mcp_resources
```

Then reference it in Hermes:

```yaml
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
      - --config
      - /path/to/opp_mcp_config.yaml
```

## Verifying the Connection

### Test with Hermes Tool Discovery

Once Hermes restarts with the new configuration, it should automatically discover the OPP tools:

- `extract_document` - Extract content from a single file
- `batch_extract` - Process multiple files at once
- `detect_format` - Identify file format
- `generate_markdown` - Convert to markdown
- `generate_xliff` - Generate XLIFF for translation

### Manual Test

Start the OPP MCP server manually to verify it works:

```bash
# Set the allowed directories
export OPP_MCP_ALLOWED_DIRS="<your-documents-dir>"

# Run the server (it will run until interrupted)
python -m opp.mcp.server
```

You should see the server start without errors. Use Ctrl+C to stop it.

## Available Tools

### extract_document

Extracts content from a document file.

```python
result = await extract_document(
    file_path="<your-documents-dir>/report.docx",
    output_formats=["md", "xlf"],
    source_lang="en",
    target_lang="zh"
)
```

Returns:
- `content` - Extracted text
- `format_type` - Document format (DOCX, PDF, etc.)
- `images_stored` - Number of images extracted
- `md_content` - Generated markdown (if requested)
- `xliff_content` - Generated XLIFF (if requested)

### batch_extract

Process multiple files in one call.

```python
result = await batch_extract(
    file_paths=[
        "<your-documents-dir>/doc1.docx",
        "<your-documents-dir>/doc2.pdf"
    ],
    output_formats=["md"]
)
```

Returns per-file results plus summary statistics.

### detect_format

Identify a file's format without extracting content.

```python
result = await detect_format(
    file_path="<your-documents-dir>/mystery.bin"
)
```

Returns `format` (e.g., "DOCX", "PDF", "UNKNOWN") and `confidence` score.

### generate_markdown

Convert a document to markdown format.

```python
result = await generate_markdown(
    file_path="<your-documents-dir>/document.docx",
    output_path="<your-output-dir>/document.md"
)
```

### generate_xliff

Generate XLIFF 1.2 format for translation workflows.

```python
result = await generate_xliff(
    file_path="<your-documents-dir>/document.docx",
    source_lang="en",
    target_lang="zh",
    output_path="<your-output-dir>/document.xlf"
)
```

Note: XLIFF generation is not supported for PDF files.

## Security

### Path Allowlist

The MCP server validates all file paths against the configured allowlist. Requests for files outside this list are rejected before any processing occurs.

### Blocked Operations

The server blocks:
- Path traversal attacks (`../etc/passwd`)
- System directories (`/etc`, `/usr`, `C:\Windows`)
- Executable files (`.exe`, `.bat`, `.sh`, `.ps1`)
- Files larger than the configured limit (default 100MB)

### Best Practices

1. **Minimal allowlist** - Only include directories the agent genuinely needs
2. **No system directories** - Never add `/`, `/home`, or `C:\` to the allowlist
3. **Separate input/output** - Use different directories for source and output
4. **Size limits** - Adjust `max_file_size_bytes` based on your document sizes

## Troubleshooting

### Server fails to start

```
Error: allowed_directories cannot be empty
```

Set the `OPP_MCP_ALLOWED_DIRS` environment variable or provide a config file with `allowed_directories`.

### File not found error

```
Path validation failed: Path is not in allowlist
```

The file path is outside your configured allowlist. Move the file to an allowed directory or update your configuration.

### Path traversal blocked

```
Path validation failed: Path traversal detected
```

Your request contained `..` path components. Use absolute paths instead.

### Timeout errors

```
Extraction failed: Request timeout
```

Increase `OPP_MCP_TIMEOUT` or reduce file size. Large PDFs with many images take longer to process.

### XLIFF not supported

```
XLIFF generation failed: XLIFF not supported for PDF files
```

PDF format does not support XLIFF output. Use `output_formats=["md"]` instead.

### uvx command not found

```
command not found: uvx
```

Install `uv` package manager:

```bash
pip install uv
```

Or use Python module directly:

```yaml
mcp_servers:
  opp:
    command: python
    args:
      - -m
      - opp.mcp.server
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPP_MCP_ALLOWED_DIRS` | Yes | - | Colon-separated list of allowed directories |
| `OPP_MCP_MAX_FILE_SIZE` | No | 104857600 | Maximum file size in bytes (100MB) |
| `OPP_MCP_TIMEOUT` | No | 60 | Request timeout in seconds |
| `OPP_MCP_RESOURCE_DIR` | No | ./mcp_resources | Directory for extracted images |
| `OPP_LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Hermes Configuration Reference

```yaml
# Minimal configuration
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
    env:
      OPP_MCP_ALLOWED_DIRS: "/docs"

# Full configuration with all options
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
      - --config
      - /path/to/config.yaml
    env:
      OPP_MCP_ALLOWED_DIRS: "/docs:/output"
      OPP_MCP_MAX_FILE_SIZE: "104857600"
      OPP_MCP_TIMEOUT: "120"
      OPP_LOG_LEVEL: "DEBUG"
```

## Support

For issues with OPP itself, check:
- OPP documentation at `docs/` directory
- GitHub issues for OPP project

For Hermes configuration issues, consult the Hermes documentation for your specific setup.
