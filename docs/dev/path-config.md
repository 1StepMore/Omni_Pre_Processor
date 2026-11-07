# OPP env vars + MCP path configuration + PathValidator (moved from AGENTS.md, OPP#119)

## env vars (MCP path)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPP_MCP_ALLOWED_DIRS` | (none) | Colon/semicolon-separated allowlist of directories the MCP can read. **Required** for tool calls to succeed. |
| `OPP_ALLOWED_DIRECTORIES` | (none) | CLI only — `--resource-dir` guard (`src/opp/cli.py:496`). NOT read by the MCP server. |
| `OPP_MCP_MAX_FILE_SIZE` | `104857600` | Max input file size in bytes. |
| `OPP_MCP_TIMEOUT` | `300` | Per-tool request timeout (seconds). |
| `OPP_MCP_HOST` | `127.0.0.1` | MCP bind host (loopback only by default). |
| `OPP_MCP_PORT` | `8766` | MCP bind port (different from ORF's 8765 so both can run). |
| `OMNI_METRICS_DIR` | `/tmp/omni-metrics` | Prometheus metrics directory. |
| `MCP_SHARED_SECRET` | (none — auth disabled) | Shared-secret auth (Phase A4). |
| `OMNI_RATE_LIMIT_RPM` | `60` | Per-MCP-tool token-bucket rate limit. |
| `OMNI_RATE_LIMIT_BURST` | `10` | Token-bucket burst size. |
| `OMNI_TEST_FAKE_LLM=1` | unset | Mock LLM responses (only affects tests). |
| `OPP_OCR_LANG` | `eng` | Tesseract OCR language code for PDF/image text extraction (e.g. `chi_sim`, `jpn`, `fra`). |
| `OPP_MCP_CLEANUP_ON_SHUTDOWN` | `false` | If `true`, the MCP server recursively removes `mcp_resources/` on shutdown (SIGTERM/SIGINT/exit). Internal `opp_mcp_*` temp files are ALWAYS cleaned regardless. |
| `OPP_AUTOLOAD_DOTENV` | unset | Set to `1` to auto-load `.env` file (same as `--load-dotenv` CLI flag). |

**Critical**: `OPP_MCP_ALLOWED_DIRS` (NOT `OPP_ALLOWED_DIRECTORIES`)
is the MCP allowlist var. The latter is CLI-only.

## Path Configuration (MCP Server)

The OPP MCP server requires explicit path configuration via 
`OPP_MCP_ALLOWED_DIRS` (colon-separated paths). This controls which 
directories the server can read/write during extraction.

```bash
export OPP_MCP_ALLOWED_DIRS="/path/to/docs:/path/to/output"
```

**Security note:** OPP does not default to any directory. If 
`OPP_MCP_ALLOWED_DIRS` is unset, the server refuses to start with 
`ValueError("allowed_directories cannot be empty")`. This is a 
fail-closed design — always set this variable explicitly in production.

## PathValidator security model

The `src/opp/mcp/security.py:PathValidator` is the gatekeeper. It
checks:

1. Path is in `OPP_MCP_ALLOWED_DIRS`
2. Path is not a symlink pointing outside the allowlist
3. Path is not in `BLOCKED_EXTENSIONS` (executables: `.exe .bat .sh
   .ps1 .vbs .js`)
4. Path is in `ALLOWED_EXTENSIONS` (md, docx, pptx, xliff, xlf, xml,
   html, odt, epub, zip, plus image/audio formats)
5. File size ≤ `max_file_size_bytes`

**To add a new input format**: edit
`PathValidator.ALLOWED_EXTENSIONS` in `src/opp/mcp/security.py:62` AND
add it to the README env var table.