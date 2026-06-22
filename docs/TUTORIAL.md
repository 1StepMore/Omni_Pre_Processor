# OPP Tutorials

Four hands-on scenarios, from a 5-minute first-run to agent-driven pipelines. Each scenario is copy-pasteable. All commands assume you are at the root of `Omni_Pre_Processor/`.

> **Tip** — set `OMNI_TEST_FAKE_LLM=1` whenever you use OPP in a test context that involves downstream translation. The variable is read by the test seams, not by OPP itself; OPP does not need an LLM.

---

## 1. 5-minute Quickstart

Goal: extract a single DOCX to Markdown and look at the result.

### 1.1 Install

```bash
cd Omni_Pre_Processor
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 1.2 Run

Use the bundled `batch_test/` fixtures or your own DOCX:

```bash
opp --target-format=md --output-dir=./out batch_test/phase0_office/*.docx
```

You should see a new `out/` directory with three files per input:

```
out/
├── contract.md
├── contract_manifest.json
└── contract.skeleton.zip
```

### 1.3 Inspect the Markdown

```bash
head -40 out/contract.md
```

The file starts with a YAML frontmatter block:

```yaml
---
source_lang: zh
target_lang: en
---
```

followed by the document content in Markdown.

### 1.4 Sanity-check with the Python API

```python
from opp import DOCXExtractor

result = DOCXExtractor().extract("out/contract.docx")
print(f"Paragraphs: {len(result.paragraphs)}")
print(f"Tables: {len(result.tables)}")
print(f"Images: {len(result.images)}")
```

If you see non-zero counts, the full pipeline (detect → extract → manage resources) succeeded.

---

## 2. Translate a DOCX end-to-end (OPP → OL → ORF)

This is the canonical 3-stage pipeline. The same idea is shown in the repo root `README.md`; this tutorial adds the working-directory and verification steps.

### 2.1 The three stages

| Stage | Tool | Produces |
|-------|------|----------|
| 1. Extract | OPP | `.md`, `.xlf`, `_manifest.json`, `.skeleton.zip` |
| 2. Translate | OL | Translated `.md` and `.xlf` |
| 3. Backfill | ORF | Translated DOCX/PPTX/EPUB |

### 2.2 Set up directories

```bash
export WORK=/tmp/opp_tutorial
rm -rf $WORK && mkdir -p $WORK
```

### 2.3 Stage 1 — OPP extract

```bash
opp --target-format=both \
    --source-lang=en --target-lang=zh \
    --output-dir=$WORK/stage1 \
    batch_test/phase0_office/sample.docx
```

Verify:

```bash
ls $WORK/stage1
# → sample.md  sample.xlf  sample_manifest.json  sample.skeleton.zip
```

### 2.4 Stage 2 — OL translate

```bash
ol translate-md $WORK/stage1/sample.md \
    --source-lang en --target-lang zh \
    --output-dir $WORK/stage2
```

Verify the translated MD still parses as valid Markdown and keeps the frontmatter.

### 2.5 Stage 3 — ORF backfill

```bash
orf apply-md $WORK/stage2/sample.md \
    --target-format docx \
    --output-path $WORK/result.docx
```

The result is a Chinese-translated DOCX that mirrors the original's structure (paragraphs, tables, headings). For pixel-perfect layout including floating images, use the XLIFF path:

```bash
orf apply-xliff batch_test/phase0_office/sample.docx \
    --xliff $WORK/stage2/sample.xlf \
    --skeleton $WORK/stage1/sample.skeleton.zip \
    --output-path $WORK/result_xliff.docx \
    --format docx
```

> **Why two paths?** MD path is text-faithful but loses precise layout. XLIFF path uses the original `.skeleton.zip` so floating images, anchored drawings, and styles round-trip exactly.

---

## 3. Batch process 100 files

Goal: extract 100 mixed-format files in one run and report failures.

### 3.1 Lay out the inputs

`batch_test/` in the OPP repo already contains 100+ files spread across these sub-folders:

```
batch_test/
├── phase0_office/         # DOCX, PPTX
├── phase5_data/           # XLSX, CSV, JSON, XML
├── phase6_web/            # HTML, EPUB
├── phase7_email_image/    # EML, MSG, PNG, JPG
└── phase8_media/          # MP3, MP4, MP3.url
```

Count them:

```bash
find batch_test -type f | wc -l
```

### 3.2 Run in batch mode

```bash
opp --target-format=both \
    --source-lang=en --target-lang=zh \
    --output-dir=/tmp/batch_out \
    --report=html -o /tmp/batch_report.html \
    batch_test/
```

Flags used:
- `--report=html` writes a human-readable error report.
- `-o` redirects the report to a file rather than stdout.
- `--output-dir` is required when the input is a folder; OPP auto-creates per-file sub-directories otherwise.

### 3.3 Expected runtime

A 100-file mixed batch on a modern laptop takes 2–5 minutes. The first run is slow (Whisper model load for any audio, markitdown for YouTube, OCR for images); subsequent runs hit the content-addressed cache and finish in seconds.

### 3.4 Check the report

```bash
xdg-open /tmp/batch_report.html    # Linux
open /tmp/batch_report.html        # macOS
```

The report shows: succeeded files, failed files (with reason), warnings (e.g. low OCR confidence), and aggregate stats.

### 3.5 Force re-run (bypass cache)

```bash
opp --no-cache --target-format=both --output-dir=/tmp/batch_out2 batch_test/
```

The cache lives in `~/.omni_cache/opp/`. Clear it with `opp --clear-cache` or set `OMNI_CACHE_DIR` to redirect.

### 3.6 Resume-friendly option

If the run is interrupted (Ctrl-C, OOM, network), re-run the same command — already-processed files return from the cache in <1 second each.

---

## 4. Use OPP with Claude / Cursor / OpenCode via MCP

Goal: give an AI agent the ability to extract documents through a tool call.

### 4.1 Install the MCP server

```bash
pip install -e ".[mcp]"
```

This installs the `opp-mcp-server` console script (defined in `pyproject.toml` `[project.scripts]`).

### 4.2 Configure the allowlist

OPP's MCP server refuses any path outside the configured allowlist. Pick a directory the agent can read (and a temp dir for outputs):

```bash
export OPP_MCP_ALLOWED_DIRS="/data/documents:/tmp/opp_mcp_out"
```

> The separator is `:` (or `;` on Windows). A single path with no separator is also accepted.

### 4.3 OpenCode / Claude Desktop / Cursor config

`opencode.json` (project-scoped):

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "uvx",
      "args": ["opp-mcp-server"],
      "env": {
        "OPP_MCP_ALLOWED_DIRS": "/data/documents:/tmp/opp_mcp_out"
      }
    }
  }
}
```

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "opp-mcp-server"
    }
  }
}
```

(set `OPP_MCP_ALLOWED_DIRS` in the OS environment, or pass via the desktop client's MCP env block).

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "uvx",
      "args": ["opp-mcp-server"]
    }
  }
}
```

### 4.4 First call — `ping`

After restarting the agent, prompt it with "ping the OPP server". The agent should call `ping` and get `{ "success": true }`.

### 4.5 Real call — `extract_document`

Drop a DOCX into `/data/documents/lease.docx` and ask the agent: "Extract `/data/documents/lease.docx` to markdown and XLIFF for English→Chinese translation."

The agent should call:

```json
{
  "tool": "extract_document",
  "params": {
    "file_path": "/data/documents/lease.docx",
    "output_formats": "both",
    "source_lang": "en",
    "target_lang": "zh"
  }
}
```

The response contains `md_content` and `xliff_content` as text. The agent can:

- Display the Markdown to the user,
- Save `md_content` to disk for OL to consume next,
- Pass `xliff_content` to a translation MCP (OL) via a follow-up tool call.

### 4.6 Pipeline via MCP (full chain)

A more advanced prompt: "Extract this contract to XLIFF, translate to Chinese, and backfill to DOCX." The agent orchestrates three MCP servers:

```json
[
  { "tool": "extract_document", "params": { "file_path": "/data/contract.docx", "output_formats": "xlf", "source_lang": "en", "target_lang": "zh" } },
  { "tool": "save_skeleton",   "params": { "file_path": "/data/contract.docx", "base_name": "contract", "output_dir": "/tmp" } },
  { "tool": "ol.translate_xliff", "params": { "input_path": "/tmp/contract.xlf", "output_path": "/tmp/contract.zh.xlf", "source_lang": "en", "target_lang": "zh" } },
  { "tool": "orf.apply_xliff",  "params": { "input_file": "/data/contract.docx", "xliff_path": "/tmp/contract.zh.xlf", "output_path": "/tmp/contract.zh.docx", "format": "docx" } }
]
```

### 4.7 Securing the server with a shared secret (optional)

For multi-user or shared-host deployments:

```bash
export MCP_SHARED_SECRET="<long-random-string>"
export OPP_MCP_ALLOWED_DIRS="/data/documents:/tmp/opp_mcp_out"
```

Every tool call must then include `auth_token: "<long-random-string>"`. Without it the server returns `AUTH_FAILED`.

### 4.8 What to read next

- [API.md](API.md) — full MCP tool schemas, error codes, exit codes.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — "Path validation failed" is the #1 thing that goes wrong on first MCP setup.
- [ARCHITECTURE.md](ARCHITECTURE.md) — what happens inside the pipeline and why.
