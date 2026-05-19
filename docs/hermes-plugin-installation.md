# Installing OPP as a Hermes Plugin

This guide explains how to install OPP (Omni Pre-Processor) as a plugin for Hermes agents.

## Prerequisites

- Hermes agent installed and configured
- Python 3.10 or later
- pip or uv package manager

## Installation Steps

### 1. Install OPP with MCP Support

```bash
pip install -e ".[mcp]"
```

Or using uv:

```bash
uv pip install -e ".[mcp]"
```

This installs the `opp-mcp-server` command and the MCP package dependency.

### 2. Create the Plugin Directory

Create the Hermes plugins directory if it does not exist:

```bash
mkdir -p ~/.hermes/plugins/opp
```

### 3. Copy the Plugin Files

Copy the OPP Hermes plugin to the plugins directory:

```bash
cp -r src/opp_hermes/* ~/.hermes/plugins/opp/
```

This copies:
- `plugin.yaml` - Plugin manifest
- `SKILL.md` - Skill documentation
- `opp_tool.py` - Tool implementation
- `__init__.py` - Python package init

### 4. Verify Installation

Check that the plugin files were copied correctly:

```bash
ls -la ~/.hermes/plugins/opp/
```

You should see:
- `plugin.yaml`
- `SKILL.md`
- `opp_tool.py`
- `__init__.py`

### 5. Configure Hermes

Add OPP to your Hermes configuration file. The exact location depends on your Hermes setup, but typically it's `hermes.yaml` or `config/hermes.yaml`.

```yaml
mcp_servers:
  opp:
    command: uvx
    args:
      - opp-mcp-server
    env:
      OPP_MCP_ALLOWED_DIRS: "/path/to/documents:/path/to/output"
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

### 6. Restart Hermes

After configuring the plugin, restart Hermes to load the OPP plugin.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPP_MCP_ALLOWED_DIRS` | Yes | - | Semicolon-separated list of allowed directories |
| `OPP_MCP_MAX_FILE_SIZE` | No | 104857600 | Maximum file size in bytes (100MB) |
| `OPP_MCP_TIMEOUT` | No | 60 | Request timeout in seconds |
| `OPP_MCP_RESOURCE_DIR` | No | ./mcp_resources | Directory for extracted images |

### Setting Allowed Directories

OPP enforces a security allowlist. Only files within these directories can be accessed.

**Linux/macOS:**

```bash
export OPP_MCP_ALLOWED_DIRS="/path/to/documents:/path/to/output"
```

**Windows:**

```cmd
set OPP_MCP_ALLOWED_DIRS=C:\path\to\documents;C:\path\to\output
```

### YAML Configuration File

You can also create a dedicated OPP MCP config file:

```yaml
allowed_directories:
  - /path/to/documents
  - /path/to/output
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
    env:
      OPP_MCP_ALLOWED_DIRS: "/path/to/documents:/path/to/output"
```

## Available Tools

When installed as a Hermes plugin, the following tools become available:

- `opp_extract` - Extract content from a single file
- `batch_extract` - Process multiple files at once (via opp_extract with directory path)
- `detect_format` - Identify file format
- `generate_markdown` - Convert to markdown
- `generate_xliff` - Generate XLIFF for translation

## Supported Formats

DOCX, PPTX, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images (OCR), Audio/Video transcription, YouTube URL

## Mental Model

OPP supplements Hermes built-in extractors. Think of it as a specialized tool that handles formats the general-purpose extractors do not support.

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

## Usage Example

```yaml
# In your Hermes agent configuration
tools:
  - name: opp
    type: code
    config:
      server_command: uvx opp-mcp-server
      allowed_directories:
        - /path/to/documents
        - /path/to/output
```

Or directly via tool call:

```
opp_extract(file_path="/path/to/document.docx", output_formats=["md"])
```

## Troubleshooting

### Plugin not loading

1. Verify the plugin files exist at `~/.hermes/plugins/opp/`
2. Check that `plugin.yaml` is present and valid
3. Restart Hermes completely

### File access errors

Make sure the directories you want to access are listed in `OPP_MCP_ALLOWED_DIRS`.

### uvx command not found

If `uvx` is not available, install `uv`:

```bash
pip install uv
```

Or use Python module directly in the Hermes config:

```yaml
mcp_servers:
  opp:
    command: python
    args:
      - -m
      - opp.mcp.server
    env:
      OPP_MCP_ALLOWED_DIRS: "/path/to/documents"
```

### Server fails to start

Ensure OPP is installed with MCP support:

```bash
pip install -e ".[mcp]"
```

## Uninstallation

To remove the OPP plugin:

```bash
rm -rf ~/.hermes/plugins/opp
```

This does not uninstall the OPP Python package. To remove OPP completely:

```bash
pip uninstall opp
```