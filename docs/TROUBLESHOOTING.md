# OPP Troubleshooting

The 12 most common errors you will hit with OPP, ranked roughly by frequency. Each section has: **Symptom** → **Diagnosis** → **Fix**.

If your error is not here, check the `logs/` directory (`<repo>/logs/`) or, for MCP, the server-side logs in stderr. The MCP server is also instrumented with `prometheus_client` metrics; metrics are emitted to stderr in text format by default.

---

## 1. `OPP_PATH_DENIED` / "Path validation failed" (MCP)

**Symptom**: Every tool call returns `{"success": false, "error_code": "OPP_PATH_DENIED"}`.

**Diagnosis**: The MCP server is enforcing its `OPP_MCP_ALLOWED_DIRS` allowlist. The path you passed is either outside every allowed directory, points to a symlink, or has a non-whitelisted extension.

**Fix**:

```bash
# Make sure OPP_MCP_ALLOWED_DIRS is exported BEFORE the server starts
export OPP_MCP_ALLOWED_DIRS="/data/documents:/tmp/opp_mcp_out"
opp-mcp-server   # or restart your agent
```

Common gotchas:

- The env var is `OPP_MCP_ALLOWED_DIRS` (NOT `OPP_ALLOWED_DIRECTORIES`).
- The separator is `:` on Unix and `;` on Windows.
- If the path resolves through a symlink to a directory outside the allowlist, it is rejected.
- Allowed extensions in the MCP whitelist: `.md`, `.docx`, `.pptx`, `.pdf`, `.xliff`, `.xlf`, `.xml`, `.html`, `.odt`, `.epub`, `.zip`, `.txt`, `.xlsx`, `.csv`, `.json`, `.eml`. **`.msg`, `.png`, `.jpg`, `.ipynb`, `.url` are NOT in the MCP whitelist** even though the CLI handles them.

See `src/opp/mcp/security.py:62-65` for the live list.

---

## 2. `RATE_LIMITED` / "Too many requests" (MCP)

**Symptom**: Intermittent `{"error_code": "RATE_LIMITED"}` during a tight loop of tool calls.

**Diagnosis**: The MCP server has a token-bucket rate limiter (H5, added 2026-06-20). Default burst is small and may not match the agent's call rate.

**Fix**: Slow the agent down (insert `asyncio.sleep(0.05)` between calls) or contact the OPP team to raise the bucket size for your deployment. There is no per-tool override; the limit is server-wide.

---

## 3. `AUTH_FAILED` (MCP)

**Symptom**: `{"error_code": "AUTH_FAILED", "message": "Authentication failed: auth_token is missing or incorrect."}`

**Diagnosis**: `MCP_SHARED_SECRET` is set in the server's environment but the tool call did not include a matching `auth_token` parameter.

**Fix**: Either unset `MCP_SHARED_SECRET` for local development:

```bash
unset MCP_SHARED_SECRET
opp-mcp-server
```

or pass the matching secret in every call:

```json
{ "tool": "extract_document", "params": { "file_path": "/x.docx", "auth_token": "<the-shared-secret>" } }
```

---

## 4. CLI: `--target-format=xlf` without `--target-lang`

**Symptom**: `usage: opp [-h] ... opp: error: --target-lang is required when --target-format is 'xlf' or 'both'`

**Diagnosis**: XLIFF requires both a source and target language code to emit `<file source-language="..." target-language="...">`.

**Fix**:

```bash
opp --target-format=xlf --source-lang=en --target-lang=zh document.docx
```

If you only need Markdown, drop `--target-format` or set it to `md` and the target-lang check is skipped (it falls back to `en`).

---

## 5. PDF → XLIFF blocked

**Symptom**: `generate_xliff` returns `{"success": false, "error": "PDF to XLIFF is not supported"}` or similar.

**Diagnosis**: This is by design. PDF content does not map cleanly to XLIFF `<trans-unit>`s, so OPP explicitly blocks it (case-insensitive guard, fix landed 2026-06-21 — see `src/opp/xliff/`).

**Fix**: Use the Markdown path for PDFs:

```bash
opp --target-format=md document.pdf
# then translate the MD, then backfill via ORF
```

PDFs round-trip back to PDF through ORF `apply-md` using the markdown→PDF engine.

---

## 6. `ModuleNotFoundError: No module named 'opp'`

**Symptom**: `opp: command not found` or `ModuleNotFoundError: No module named 'opp'`.

**Diagnosis**: OPP is not installed in the active Python environment. The package is `omni-pre-processor` on PyPI; the import name is `opp`.

**Fix**:

```bash
# From source (editable)
cd Omni_Pre_Processor
pip install -e .

# Or from PyPI
pip install omni-pre-processor
```

Verify:

```bash
python -c "import opp; print(opp.__version__)"
# → 0.6.1
```

---

## 7. OCR returns empty / low-quality text

**Symptom**: A scanned PNG produces MD with empty or garbled text.

**Diagnosis**: Either Tesseract is not installed, the language pack is missing, or the image is low-DPI.

**Fix**:

```bash
# Install Tesseract
sudo apt install tesseract-ocr          # Debian/Ubuntu
brew install tesseract                  # macOS

# Install the right language pack
sudo apt install tesseract-ocr-chi-sim  # Simplified Chinese
sudo apt install tesseract-ocr-eng      # English (often default)

# Specify the language explicitly
opp --ocr-engine=tesseract --ocr-lang=chi_sim scan.png
```

For non-Latin scripts, prefer RapidOCR (`pip install -e ".[ocr]"` + `--ocr-engine=rapidocr`); it is a single-binary download and has broader language support.

---

## 8. `extract_document` response is huge, agent runs out of context

**Symptom**: A 200-page DOCX returns 50MB of `md_content` and the agent's context window overflows.

**Diagnosis**: OPP returns the full text in one tool response (the alternative would be a 200-line tool call to page through it).

**Fix**: Pre-chunk the document, or save the response to a file and pass the file path to the next tool. Example:

```python
# After calling extract_document:
import json, pathlib
result = call_tool("extract_document", file_path=path)
pathlib.Path("/tmp/doc.md").write_text(result["md_content"])
# Now point downstream tools at /tmp/doc.md instead of embedding in context
```

For 200+ page documents, the OPP chunke r (`src/opp/chunker.py`) is also available as a Python API.

---

## 9. `--resource-dir` rejected by the CLI

**Symptom**: `opp: error: --resource-dir '/var/www' is not within allowed directories.`

**Diagnosis**: The CLI allows `--resource-dir` only under CWD, `/tmp`, or paths listed in `OPP_ALLOWED_DIRECTORIES`. This is a security guard (B1, added 2026-06) to prevent path-traversal exfiltration.

**Fix**:

```bash
# Option A: Use a path under CWD
opp --target-format=md --resource-dir=./resources --output-dir=./out file.docx

# Option B: Allow /tmp explicitly
opp --resource-dir=/tmp/myresources --output-dir=./out file.docx

# Option C: Extend the allowlist
export OPP_ALLOWED_DIRECTORIES="/var/www,/srv/data"
opp --resource-dir=/var/www/opp --output-dir=./out file.docx
```

Note: this is a different env var than the MCP one (`OPP_MCP_ALLOWED_DIRS`).

---

## 10. `OPP_FILE_NOT_FOUND` after the input file clearly exists

**Symptom**: The MCP server returns `OPP_FILE_NOT_FOUND` even though `ls` shows the file.

**Diagnosis**: The file path passed in the tool call is inside an allowed directory, but contains a non-whitelisted extension (e.g. `.msg` or `.png`). The validator runs in this order: path traversal → directory allowlist → symlink → extension whitelist → existence.

**Fix**: Either rename the file to a whitelisted extension, or call `detect_format_tool` first to confirm the file is readable, then contact the OPP team to extend the MCP whitelist. The CLI has a broader whitelist (see `src/opp/cli.py:262-263`).

---

## 11. `Bad magic number` or `zipfile.BadZipFile` on a DOCX

**Symptom**: `Error processing /path/file.docx: BadZipFile: File is not a zip file`.

**Diagnosis**: The file is corrupted, password-protected, or is not actually a DOCX (maybe it has a `.docx` extension but is plain text or a Google Docs export).

**Fix**:

```bash
# Verify the file type
file /path/file.docx
# Expected: "Microsoft OOXML"

# Re-detect via OPP's own detector
opp --detect-format /path/file.docx
# If this returns UNKNOWN, the file is not what its extension claims
```

If the file is genuinely a Google Docs export, open it in Google Docs and re-save as `.docx` (the export adds a normal OOXML wrapper).

---

## 12. Cache returns stale results after a content edit

**Symptom**: You re-run OPP after editing the source file, but the output is identical to the previous run.

**Diagnosis**: OPP's content-addressed cache (A6, in `~/.omni_cache/opp/`) keys on `sha256(file_bytes + config_file_hash)`. The file content is hashed, so genuine edits should miss the cache. If the hash is unchanged, the file bytes really are unchanged.

**Fix**:

```bash
# Bypass the cache for this run
opp --no-cache --target-format=both file.docx

# Or clear it entirely
opp --clear-cache

# Or override the cache root
OMNI_CACHE_DIR=/tmp/fresh_cache opp --target-format=both file.docx
```

The cache stores only the produced `.xlf`. If you asked for `--target-format=md` or `both`, the cache is bypassed automatically (so re-running MD is always fresh).

---

## 13. (Bonus) MCP server starts but every tool call times out

**Symptom**: `asyncio.TimeoutError` or `OPP_TIMEOUT` from any tool call.

**Diagnosis**: Default `request_timeout_seconds` is 60s. Large PDF or PPTX files with hundreds of slides or images can exceed this on slow hardware.

**Fix**: Raise the server-side timeout:

```bash
export OPP_MCP_TIMEOUT=600
opp-mcp-server
```

Or pre-process with `--max-file-size` to skip the largest files:

```bash
export OPP_MCP_MAX_FILE_SIZE=$((50*1024*1024))  # 50MB cap
```

---

## 14. (Bonus) Test suite imports from `opp` but the test environment uses `omni-pre-processor`

**Symptom**: `ImportError: No module named 'opp'` inside a CI runner that did `pip install omni-pre-processor`.

**Diagnosis**: There is no inconsistency. The PyPI distribution name (`omni-pre-processor`) differs from the import name (`opp`) on purpose — see `pyproject.toml:2-7`. The README at the project root calls this out: import `opp`, install `omni-pre-processor`.

**Fix**:

```bash
pip install omni-pre-processor
python -c "import opp; print(opp.__version__)"   # → 0.6.1
```

This is intentional. The original PyPI name `opp` collides with PAY.ON's payment-processing library.
