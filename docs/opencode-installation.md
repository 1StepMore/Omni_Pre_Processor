# Installing OPP as an OpenCode Skill

This guide explains how to install OPP (Omni Pre-Processor) as an OpenCode skill, enabling AI assistants to extract content from documents.

## Prerequisites

- OpenCode installed
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

### 2. Copy the Skill File

Create the OpenCode skills directory if it does not exist:

```bash
mkdir -p ~/.config/opencode/skills/
```

Copy the OPP agent skill to the skills directory:

```bash
cp -r src/opp_agent ~/.config/opencode/skills/
```

The skill file is located at:

```
~/.config/opencode/skills/opp_agent/SKILL.md
```

### 3. Verify Installation

Check that the skill was copied correctly:

```bash
ls -la ~/.config/opencode/skills/opp_agent/
```

You should see the `SKILL.md` file in the output.

### 4. Restart OpenCode

After copying the skill, restart OpenCode to load the new skill.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPP_MCP_ALLOWED_DIRS` | Yes | - | Colon-separated list of allowed directories |
| `OPP_MCP_MAX_FILE_SIZE` | No | 104857600 | Maximum file size in bytes (100MB) |
| `OPP_MCP_TIMEOUT` | No | 60 | Request timeout in seconds |
| `OPP_MCP_RESOURCE_DIR` | No | ./mcp_resources | Directory for extracted images |

### Setting Allowed Directories

OPP enforces a security allowlist. Only files within these directories can be accessed. Set the environment variable before running OpenCode:

**Linux/macOS:**

```bash
export OPP_MCP_ALLOWED_DIRS="/path/to/documents:/path/to/output"
```

**Windows (Command Prompt):**

```cmd
set OPP_MCP_ALLOWED_DIRS=C:\path\to\documents;C:\path\to\output
```

**Windows (PowerShell):**

```powershell
$env:OPP_MCP_ALLOWED_DIRS = "C:\path\to\documents;C:\path\to\output"
```

### Configuration File

You can also create a YAML configuration file:

```yaml
allowed_directories:
  - /path/to/documents
  - /path/to/output
  - ./documents

max_file_size_bytes: 104857600
request_timeout_seconds: 60
resource_storage_dir: ./mcp_resources
```

## Available Tools

When installed as an OpenCode skill, the following tools become available:

- `extract_document` - Extract content from a single file
- `batch_extract` - Process multiple files at once
- `detect_format` - Identify file format
- `generate_markdown` - Convert to markdown
- `generate_xliff` - Generate XLIFF for translation

## Supported Formats

DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images (OCR), Audio/Video transcription, YouTube URL

## Usage Example

```
extract_document(file_path="/path/to/document.docx", output_formats=["md"])
```

## Troubleshooting

### Skill not appearing after installation

1. Verify the skill file exists at `~/.config/opencode/skills/opp_agent/SKILL.md`
2. Restart OpenCode completely
3. Check that the `OPP_MCP_ALLOWED_DIRS` environment variable is set

### File access errors

Make sure the directories you want to access are listed in `OPP_MCP_ALLOWED_DIRS`.

### Server fails to start

Ensure OPP is installed with MCP support:

```bash
pip install -e ".[mcp]"
```

## Uninstallation

To remove the OPP skill:

```bash
rm -rf ~/.config/opencode/skills/opp_agent
```

This does not uninstall the OPP Python package. To remove OPP completely:

```bash
pip uninstall opp
```