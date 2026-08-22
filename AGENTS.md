# AGENTS.md — Omni_Pre_Processor (OPP)

Developer + agent context for the **OPP** sub-repo. The suite-level
[suite-level AGENTS.md](https://github.com/1StepMore/e2e-test-suite/blob/main/AGENTS.md) covers cross-module
orchestration (OPP → OL → ORF); this file is for working **inside**
OPP.

> OPP is the first step of the Omni Suite pipeline. It extracts
> documents (DOCX/PPTX/PDF/HTML/EPUB/EML/MSG/images/…) into
> standardized **Markdown + XLIFF + skeleton.zip** for downstream
> translation and backfill.

> **Prerequisite:** Python >= 3.13. Verify with `python3 --version`.

## Quick start

```bash
# Install
bash scripts/setup_dev.sh

# CLI: extract a DOCX
opp document.docx --target-format both --output-dir /tmp/out

# CLI: extract with explicit language pair
opp document.docx --target-format both --source-lang en --target-lang zh

# MCP server (stdio)
opp mcp             # or: python -m opp.mcp.server

# Tests
make test           # runs uv run pytest tests/ -v
```

## Source layout

```
src/opp/
├── cli.py                # `opp` CLI entry
├── pipeline.py           # OPPPipeline orchestrator
├── detector.py           # Magic-bytes format detection
├── extractors/           # One extractor per input format
│   ├── docx.py           # python-docx-based DOCX extraction
│   ├── pptx.py           # python-pptx-based PPTX extraction
│   ├── pdf.py            # PDF (pypdf + pdfplumber)
│   ├── xlsx.py           # openpyxl
│   ├── csv.py            # pandas (E2E-81: now warns on bad lines)
│   ├── json.py, xml.py   # Pure Python
│   ├── html.py           # readability + docling (E2E-82: falls back)
│   ├── epub.py           # ebooklib
│   ├── email.py          # email stdlib (EML/MSG)
│   ├── image_ocr.py      # Tesseract / RapidOCR
│   ├── youtube.py        # markitdown[youtube-transcription]
│   └── …
├── channels/            # Output formatters (MD / XLIFF)
│   ├── md_bus.py         # MD output bus
│   ├── table_channel.py  # DataFrame → MD table
│   ├── xliff/            # XLIFF 1.2 / 2.0 generators
│   └── markdown/         # MDGenerator (E2E-75: is_inline_in_md)
├── mcp/                  # MCP server (the Agent-facing surface)
│   ├── server.py         # Standard mcp library, 9 tools
│   ├── config.py         # MCPConfig dataclass (E2E-76: reads OPP_MCP_*)
│   ├── security.py       # PathValidator
│   ├── auth.py           # MCP_SHARED_SECRET auth
│   └── rate_limiter.py   # Per-MCP-tool token bucket
├── resource_manager.py   # Image dedup (MD5 + UUID naming)
├── parsers/              # frontmatter + XLIFF parsers
└── config/               # YAML config + loaders
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `opp <file> --target-format md|xliff|both --output-dir <dir>` | Extract a single document |
| `opp <file> --source-lang en --target-lang zh` | Specify language pair (otherwise uses config defaults) |
| `opp <file> --no-embed-images` | Don't base64-inline images into the MD (E2E-05 style) |
| `opp <file> --style-map '{"a5":1}'` | Promote paragraph style `a5` to H1 (pandoc) |
| `opp --detect-format <file>` | Format detection only |
| `opp -v <file> …` | Verbose (writes to **stderr** since v0.6.2) |
| `opp mcp` | Start the MCP server (stdio) |
| `opp --batch <file1> <file2> …` | Batch extract |

## MCP tools (9 total)

| Tool | Purpose |
|------|---------|
| `extract_document` | Extract content from a single document file. Supports all 13 input formats. |
| `batch_extract` | Process multiple files in one request. |
| `detect_format_tool` | Identify file format using magic bytes. |
| `generate_markdown` | Convert a document to Markdown (no XLIFF / skeleton). |
| `generate_xliff` | Convert a document to XLIFF 1.2 / 2.0. |
| `save_skeleton` | Save the skeleton.zip for an extracted document (required by ORF `apply-xliff`). |
| `ping` | Health check (returns version). |

For full per-tool parameter reference, see the suite-level
[AGENTS.md → MCP Tool Reference](https://github.com/1StepMore/e2e-test-suite/blob/main/AGENTS.md) table,
or [agent-pipeline-guide.md](https://github.com/1StepMore/e2e-test-suite/blob/main/docs/agent-pipeline-guide.md).

## Extractor architecture

Each format has a dedicated extractor under `src/opp/extractors/`.
All extractors share the same base class `ExtractorBase`
(`src/opp/extractors/base.py`) which defines:

```python
class ExtractorBase:
    def supported_extensions(self) -> list[str]: ...
    def extract(self, input_path: Path) -> ExtractionResult: ...
    def validate_file(self, input_path: Path) -> None: ...
    def get_file_info(self, input_path: Path) -> DocumentMetadata: ...
```

`ExtractionResult` (in `src/opp/utils/dataclasses.py`) carries:
- `paragraphs: list[ParagraphData]`
- `tables: list[TableData]`
- `images: list[ImageData]` (with `is_floating`, `wp_anchor_h/v`, `is_inline_in_md` since v0.6.0/0.6.4)
- `metadata: DocumentMetadata`
- `warnings: list[str]`
- `skeleton: bytes | None` (the skeleton.zip for ORF)

**To add a new extractor**:

1. Create `src/opp/extractors/<format>.py` with a class
   extending `ExtractorBase`
2. Implement `supported_extensions()` and `extract()`
3. Register it in `src/opp/extractors/__init__.py`
4. Add tests in `tests/test_<format>_extractor.py`
5. Add the format to `src/opp/detector.py` magic-bytes table
6. If it produces images, emit `ImageData(is_inline_in_md=...)` correctly
   so `MarkdownGenerator` dedup works (E2E-75)

## Image pipeline

OPP emits image references into the MD output via two paths:

1. **Inline images** (`ImageData.element_index` set) — written into
   the MD paragraph by `MarkdownGenerator._escape_inline`.
2. **DOCX drawings** (`ImageData.paragraph_index` or
   `is_floating=True`) — preserved in skeleton.zip; ORF reinjects
   during `apply-xliff`.

For HTML inputs, `is_inline_in_md=True` is set for every image
because `_html_to_markdown` (via `markdownify`) already embeds
`![…](src)` refs. Without this flag, `MarkdownGenerator` would
double-embed the same image (E2E-75).

For DOCX floating drawings, `ImageData.is_floating=True` and
`wp_anchor_h` / `wp_anchor_v` (in EMU) carry the position so ORF
can rebuild `<wp:anchor>` blocks.

## XLIFF output schema

`src/opp/xliff/generator.py` produces XLIFF 1.2 or 2.0. Each
`<trans-unit>` carries the source text + inline tags (`<bx>` / `<ex>` /
`<it>`) for format preservation. ORF's `apply-xliff` reverses the
process.

`Pipeline.is_complete()` (in `src/ol_xliff/repair/pipeline.py` — OL
side, not OPP) validates the XLIFF is fully translated.

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

## PDF / XLIFF limitation

**PDF → XLIFF is intentionally blocked.** OPP can extract PDF → MD
(via pypdf + pdfplumber), but `generate_xliff` raises on PDF input
because PDF structure is too lossy for clean XLIFF `<trans-unit>`
extraction. Use the MD path with a downstream translation step
that produces a new XLIFF, or translate the MD directly.

## Skeleton preservation

For DOCX/PPTX/EPUB, OPP also produces a `skeleton.zip` alongside
the XLIFF. It contains the original ZIP structure (DOCX = `word/`,
`[Content_Types].xml`; PPTX = `ppt/slides/`, `ppt/media/`; EPUB =
`OEBPS/`, `META-INF/`). ORF's `apply-xliff` reads the skeleton to
re-inject translated text without re-rendering styles or losing
media.

## Known issues / gotchas

- **E2E-15**: `MarkdownGenerator` filters out orphan images. If an
  image has no paragraph anchor, it goes to the trailing `## Images`
  block instead of being inlined.
- **E2E-75**: HTML input → every image is `is_inline_in_md=True`
  (markdownify already embedded the ref). `MarkdownGenerator`
  dedup checks this flag and skips the generator's own inline
  injection + the trailing `## Images` block.
- **E2E-81**: CSV input with quoted multi-line cells now passes
  through cleanly. `pd.read_csv(on_bad_lines="warn")` surfaces
  mis-parses; `_escape_table_cell` escapes `\n` as `<br>` for
  pandoc tables.
- **E2E-82**: `HTMLExtractor` now falls back to readability when
  docling raises or returns empty. Previously a docling OOM/timeout
  produced a 0-character `.md` with no error.
- **`opp -v`** writes to stderr (since v0.6.2) — so MCP logging
  doesn't capture it.
- **PDF→XLIFF** is blocked by design (see above).
- **`.url` (YouTube)**: auto-detected and routed to
  `markitdown[youtube-transcription]`. Requires the `[youtube]`
  extra.

## Tests

```bash
make test                            # all tests via uv run pytest tests/ -v
pytest tests/test_html_extractor.py  # HTML extractor only
pytest tests/test_e2e_75_html_image_dedup.py  # specific E2E regression
```

Coverage target ≥90% (per `pyproject.toml [tool.coverage]`).

Key test files:
- `tests/test_html_extractor.py` — HTML extractor (readability/docling)
- `tests/test_md_generator.py` — MD output format
- `tests/test_xliff_generator.py` — XLIFF 1.2/2.0
- `tests/test_e2e_75_html_image_dedup.py` — image dedup regression
- `tests/test_e2e_81_csv_multiline.py` — multi-line CSV cells
- `tests/test_e2e_82_docling_fallback.py` — docling fallback
- `tests/test_resource_manager.py` — image MD5+UUID naming
- `tests/test_pipeline.py` — end-to-end pipeline integration

### --target-format Selection Guide

Choose `--target-format` based on your downstream pipeline:

| Flag | Produces | Downstream | Best for |
|------|----------|------------|----------|
| `md` | `.md` file | OL `translate-md` → ORF `apply-md` | Fast text output, 16 output formats |
| `xlf` | `.xlf` + `skeleton.zip` | OL `translate-xliff` → ORF `apply-xliff` | Original layout preservation |
| `both` | `.md` + `.xlf` + `skeleton.zip` | Either path | Maximum flexibility |

**Decision flow:**

1. Need clean text fast, or converting to a different format? → **`md`**
2. Need the output to look exactly like the source? → **`xlf`** (requires skeleton.zip)
3. Not sure yet? → **`both`** (costs extra extraction time, but keeps options open)

**Caveats:**
- PDF → XLIFF is intentionally blocked (see [PDF / XLIFF limitation](#pdf--xliff-limitation) above)
- skeleton.zip is only produced for DOCX/PPTX/EPUB inputs
- `both` runs MD generation + XLIFF generation, roughly doubling extraction time

**Full pipeline comparison**: See the suite-level
[Pipeline Selection Strategy](https://github.com/1StepMore/e2e-test-suite/blob/main/README.md#pipeline-selection-strategy)
for the complete decision tree and format support matrix.

## Pointers to the suite-level docs

- Cross-module orchestration: [AGENTS.md](https://github.com/1StepMore/e2e-test-suite/blob/main/AGENTS.md)
- MCP tool full parameter reference: [agent-pipeline-guide.md](https://github.com/1StepMore/e2e-test-suite/blob/main/docs/agent-pipeline-guide.md)
- Pre-commit hooks: [.pre-commit-config.yaml](https://github.com/1StepMore/e2e-test-suite/blob/main/.pre-commit-config.yaml)
- Compatibility matrix: [COMPATIBILITY.md](https://github.com/1StepMore/e2e-test-suite/blob/main/COMPATIBILITY.md)
- OPP's own per-Agent skill files: `src/opp_agent/SKILL.md`
  (OpenCode) and `src/opp_hermes/SKILL.md` (Hermes) — supplementary
  tool-level references.

## How to validate this module

OPP ships its own validation scenario library **in this repo** at
`scenarios/` — 6 tier-1 `opp-extraction` scenarios (format detection, CLI
extraction, JSON→XLIFF regression, MCP tool calls, error handling) with
their own `scenarios/STANDARDS.md` + `scenarios/_fixtures/`. The suite
validation engine runs them via `--repo opp`. The suite's own
`tool-opp-*` agent-surface scenarios (MCP tool contracts) still live in
the suite repo and are covered by the suite-level `--module opp` filter.
Any agent or the human director can validate OPP in isolation:

```bash
# From the Omni Suite root (clone: https://github.com/1StepMore/e2e-test-suite)
source .venv_ol/bin/activate

# List OPP's in-repo scenarios
python scripts/validation/run_validation.py --repo opp --list

# Run OPP's in-repo hermetic scenarios (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --repo opp --tier 1

# Or use the suite-level module filter (adds tool-opp-* agent-surface scenarios)
python scripts/validation/run_validation.py --module opp --tier 1

# Coverage: every OPP MCP tool must be scenario-exercised
python scripts/validation/coverage_audit.py   # opp row must show 9/9, 0 missing
```

The standards bar is `scenarios/STANDARDS.md` (AGENT-SURFACE family:
tool-contract, json-parseable, error-clarity, path-security, exit-codes).
Director loop + 10-minute checklist: `docs/dev/validation-director-loop.md`
in the suite repo. Per-repo validation delivery (run_meta, report card,
delivery package): `docs/dev/per-repo-validation-delivery.md`. OPP
scenario fixes now live HERE (in `scenarios/`); OPP product-code fixes
go through the normal fix cycle in this repo.
