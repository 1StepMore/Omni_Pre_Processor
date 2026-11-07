# OPP MCP tools reference (moved from AGENTS.md, OPP#119)

OPP exposes 9 MCP tools (the Agent-facing surface):

| Tool | Purpose |
|------|---------|
| `extract_document` | Extract content from a single document file. Supports all 16 input formats. |
| `batch_extract` | Process multiple files in one request. |
| `detect_format_tool` | Identify file format using magic bytes. |
| `generate_markdown` | Convert a document to Markdown (no XLIFF / skeleton). |
| `generate_xliff` | Convert a document to XLIFF 1.2 / 2.0. |
| `save_skeleton` | Save the skeleton.zip for an extracted document (required by ORF `apply-xliff`). |
| `validate_xliff` | Validate an XLIFF 1.2 file against the OASIS XSD schema and the trans-unit content rules. |
| `get_capabilities` | Return OPP module capabilities: supported input formats, output formats, and available MCP tools. |
| `ping` | Health check (returns version). |

For full per-tool parameter reference, see this module's [`docs/API.md`](../API.md).
The suite-level [agent-pipeline-guide.md](https://github.com/1StepMore/e2e-test-suite/blob/main/docs/agent-pipeline-guide.md)
covers server/tool inventory and namespacing.