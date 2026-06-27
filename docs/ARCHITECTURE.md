> **Note:** This file covers OPP internals only. For cross-module pipeline architecture
> (OPP → OL → ORF), see the [suite-level ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

# OPP Architecture

A walk-through of how the Omni Pre-Processor is built, the data flow inside a single extraction, the design decisions encoded in the source, and the formats supported on both ends.

For the operator-facing quickstart, see [README.md](../README.md). For the function-level API surface, see [API.md](API.md). For step-by-step usage, see [TUTORIAL.md](TUTORIAL.md).

---

## 1. Module diagram

```
                        ┌──────────────────────────────────────────────┐
                        │                  CLI / MCP                    │
                        │    (argparse in cli.py  /  mcp.server.Server) │
                        └───────────────────┬──────────────────────────┘
                                            │ argparse.Namespace / dict
                                            ▼
                        ┌──────────────────────────────────────────────┐
                        │               OPPPipeline                    │
                        │  process_file() → generate_markdown/xliff     │
                        │  save_skeleton() → generate_images_json()     │
                        └────┬──────────────┬──────────────┬────────────┘
                             │              │              │
                             ▼              ▼              ▼
                  ┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
                  │   detector.py   │ │  extractors/ │ │resource_manager│
                  │  FormatType enu │ │ 16 backends  │ │ MD5 + UUID     │
                  │ magic bytes     │ │ per format   │ │ image dedup    │
                  └─────────────────┘ └──────┬───────┘ └────────────────┘
                                             │
                            ┌────────────────┼─────────────────┐
                            │                │                 │
                            ▼                ▼                 ▼
                     ┌────────────┐  ┌──────────────┐  ┌──────────────┐
                     │ markdown/  │  │   xliff/     │  │  channels/   │
                     │ MarkdownGen│  │ XLIFF 1.2/2.0│  │ table, kv    │
                     │ YAML front │  │ <bx>/<ex>    │  │ DataFrame→MD │
                     │ matter     │  │ inline tags  │  │ dict→XLIFF   │
                     └────────────┘  └──────────────┘  └──────────────┘

External sub-packages used by the extractors:
  python-docx, python-pptx, pymupdf, openpyxl, beautifulsoup4, ebooklib,
  extract-msg, faster-whisper, markitdown[youtube-transcription], rapidocr-onnxruntime
```

---

## 2. Data flow

A single `OPPPipeline.process_file(path)` call walks these stages in order:

```
        path
          │
          ▼
   ┌──────────────┐
   │ detector.py  │   1. Read 8 bytes, magic-bytes detection
   │ FormatType + │   2. Fall back to extension (with confidence 0.5)
   │ confidence   │   3. UNKNOWN if neither matches
   └──────┬───────┘
          │ FormatType
          ▼
   ┌──────────────────────┐
   │  extractors/<fmt>    │   4. Dispatch by FormatType to a backend:
   │  base.ExtractorBase  │      - DOCX → python-docx (paragraphs, tables, runs, drawings)
   │                      │      - PDF  → pymupdf (text blocks, images per page)
   │  → ExtractionResult  │      - PPTX → python-pptx (slides, shapes, notes)
   │   - paragraphs[]     │      - XLSX → openpyxl (sheets, rows, merged cells)
   │   - tables[]         │      - CSV/JSON/XML → table_channel or keyvalue_channel
   │   - images[]         │      - HTML/EPUB → beautifulsoup4 / ebooklib
   │   - slides[] (PPTX)  │      - EMAIL/EML → stdlib email + attachment recursion
   │   - warnings[]       │      - MSG → extract-msg (with header fallbacks)
   │   - metadata         │      - IMAGE → tesseract or rapidocr
   │                      │      - AUDIO/VIDEO → faster-whisper
   │                      │      - IPYNB → nbformat
   │                      │      - YOUTUBE → markitdown youtube-transcription
   └──────┬───────────────┘
          │ ExtractionResult
          ▼
   ┌──────────────────────┐
   │ resource_manager.py  │   5. For each Image:
   │ MD5 + UUID, dedup    │      - hash bytes, lookup in registry
   │                      │      - if new: write to <storage>/<uuid>.<ext>
   │                      │      - if duplicate: reuse existing file
   │                      │   6. Floating drawings get is_floating=True
   │                      │      with wp_anchor_h / wp_anchor_v (EMU)
   └──────┬───────────────┘
          │ ExtractionResult + image refs
          ▼
   ┌──────────────────────┐
   │   Output formatters  │   7a. markdown/generator.py → <stem>.md
   │   (called by CLI     │       (YAML frontmatter, headings, tables,
   │    or MCP layer)     │        base64-embedded or linked images)
   │                      │   7b. xliff/XLIFFFileGenerator → <stem>.xlf
   │                      │       (XLIFF 1.2, <bx>/<ex> inline tags)
   │                      │   7c. skeleton ZIP → <stem>.skeleton.zip
   │                      │       (preserved DOCX/PPTX internals)
   │                      │   7d. images JSON → <stem>_images.json
   └──────┬───────────────┘
          │
          ▼
       manifest.json
```

The CLI wraps this in `process_single_file()` (`src/opp/cli.py:312`) and additionally writes `<stem>_manifest.json` with source info, hashes, and counts.

---

## 3. Key design decisions (ADRs)

### ADR-1: Magic-bytes detection with extension fallback

**Decision** — `FormatType` is decided by reading the first 8 bytes of the file. Extension is used as a secondary signal (confidence 0.5) only when magic bytes are ambiguous (e.g. all `PK` ZIPs).

**Why** — Renamed files (`report.docx` that is actually a PDF) are still extracted correctly. Users with weird upstream pipelines don't have to rename files before they work.

**Trade-off** — A renamed PDF inside a directory filter won't be filtered by extension. The CLI's `expand_directories` does still filter by extension, so the detector only sees pre-filtered files in batch mode.

### ADR-2: XLIFF inline tags (`<bx>`/`<ex>`) instead of CSS/HTML

**Decision** — Inline formatting (bold, italic, underline, strikethrough) is encoded in XLIFF as paired `<bx id="N"/>` open and `<ex id="N"/>` close tags.

**Why** — XLIFF 1.2 is the de-facto CAT-tool standard. The `<bx>/<ex>` convention is what OmegaT, memoQ, and SDL Trados round-trip natively. HTML/Markdown would lose structural information that ORF needs to rebuild the original document.

**Trade-off** — Tools that don't understand the convention may show raw tags in preview. ORF's `apply_xliff` strips them and re-injects the original formatting.

### ADR-3: `skeleton.zip` for high-fidelity backfill

**Decision** — For DOCX/PPTX inputs, OPP saves a copy of the original ZIP structure as `<stem>.skeleton.zip`. ORF's `apply_xliff` uses this to write the translated DOCX/PPTX by editing the preserved internals (rather than re-zipping from scratch).

**Why** — A regenerated DOCX loses floating-image anchors, custom styles, embedded media, and document-property metadata. The skeleton lets ORF do a precise in-place edit.

**Trade-off** — The skeleton can be 10–100× larger than the XLIFF. Storage cost is real for very large archives.

### ADR-4: Two output paths — MD (text-faithful) and XLIFF (layout-faithful)

**Decision** — `--target-format=md` produces a single Markdown file with images either inlined (base64) or in a sibling directory. `--target-format=xlf` produces XLIFF + skeleton for ORF round-trip.

**Why** — Most users want fast text extraction; a smaller subset needs pixel-perfect layout preservation. Forcing one path on everyone means choosing the wrong default for at least half.

**Trade-off** — Beginners sometimes pick the wrong path and get surprised. Tutorials and the `manifest.json` are designed to make the choice obvious.

### ADR-5: Content-addressed cache keyed on file bytes + config hash

**Decision** — Re-runs of `opp` on the same file with the same config (currently `config/default.yaml`; legacy `opp_config.yaml` is deprecated) skip extraction and copy the cached `.xlf` directly. Implemented in `cli.py:34-96` (A6, 2026-06).

**Why** — A 100-file batch interrupted at file 73 should resume in seconds, not minutes. CI pipelines that re-run on the same fixture also benefit.

**Trade-off** — `--target-format=md` is intentionally not cached (Markdown is fast enough; users expect fresh output). Only XLIFF outputs are cached.

### ADR-6: Path security is layered (traversal, symlink, allowlist, extension, size)

**Decision** — `PathValidator` (`src/opp/mcp/security.py`) runs five independent checks in order. Any failure is reported as `OPP_PATH_DENIED`.

**Why** — A single check is bypassable. Defense in depth means an attacker would need to defeat all five simultaneously.

**Trade-off** — Onboarding friction. The `OPP_MCP_ALLOWED_DIRS` env var must be set correctly, and the extension whitelist is more restrictive than the CLI's. This is the #1 source of "why doesn't MCP work" — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#1-opp_path_denied--path-validation-failed-mcp).

### ADR-7: Standard `mcp.server.Server` instead of FastMCP

**Decision** — The MCP layer uses the `mcp` library's `Server` + `stdio_server` (not `fastmcp`).

**Why** — FastMCP 3.4.2 has a stdio-transport bug where it reads stdin but never writes responses. The standard library's transport is reliable. The fix was committed 2026-06-22 and applies to all three Omni modules. See the suite-level `learnings.md` for the full root-cause analysis.

### ADR-8: Renamed PyPI distribution, unchanged import name

**Decision** — PyPI distribution is `omni-pre-processor`; the Python import is still `opp`. Console scripts are still `opp` and `opp-mcp-server`.

**Why** — The PyPI name `opp` is owned by PAY.ON's payment-processing library. Renaming the distribution lets us publish without colliding; the import name stays so all `from opp import ...` calls in downstream consumers keep working.

**Trade-off** — Users following old tutorials that say `pip install opp` will be confused. The README at the project root calls this out explicitly.

---

## 4. Supported input formats (16)

Detection is magic-bytes-first, extension-fallback. Confidence 1.0 = magic-bytes match, 0.5 = extension-only.

| # | Format | `FormatType` | Extractor | Detection signal | Notes |
|---|--------|--------------|-----------|------------------|-------|
| 1 | DOCX | `docx` | `extractors/docx.py` | `PK` + `.docx` | Inline formatting preserved |
| 2 | PPTX | `pptx` | `extractors/pptx.py` | `PK` + `.pptx` | Slide-by-slide, with notes |
| 3 | PDF | `pdf` | `extractors/pdf.py` | `%PDF-` | Text + images, page-by-page |
| 4 | XLSX | `xlsx` | `extractors/xlsx.py` | `PK` + `.xlsx` | Sheets, rows, merged cells |
| 5 | CSV | `csv` | `extractors/csv.py` | extension | Chardet for encoding |
| 6 | JSON | `json` | `extractors/json.py` | extension or `{` | keyvalue_channel |
| 7 | XML | `xml` | `extractors/xml.py` | extension or `<` | structure preserved |
| 8 | HTML | `html` | `extractors/html.py` | `<html` | via beautifulsoup4 |
| 9 | EPUB | `epub` | `extractors/epub.py` | `PK` + `.epub` | via ebooklib |
| 10 | EML | `email` | `extractors/email.py` | RFC 822 headers | attachment recursion |
| 11 | MSG | `email` | `extractors/email.py` | OLE compound (`D0CF11E0`) | via extract-msg |
| 12 | Image | `image` | `extractors/image_ocr.py` | PNG/JPEG/TIFF/BMP magic | Tesseract or RapidOCR |
| 13 | Audio | `audio` | `extractors/audio.py` | MP3/WAV/FLAC | faster-whisper ASR |
| 14 | Video | `video` | `extractors/video.py` | MP4/MKV | ffmpeg + whisper |
| 15 | IPYNB | `ipynb` | `extractors/ipynb.py` | `.ipynb` JSON shape | cells + outputs |
| 16 | YouTube | `youtube` | `extractors/youtube.py` | URL match in `.url` file | markitdown youtube-transcription |

`.url` files (Windows Internet Shortcut) are auto-detected as YouTube: the detector reads the first line and matches against `YOUTUBE_URL_PATTERN` in `detector.py:7-9`.

---

## 5. Supported output formats (15)

The Markdown output is internally rich (heading levels, tables, images, code blocks, blockquotes, YAML frontmatter). ORF re-parses it back into 15 different final formats.

| # | Output | Path | Engine | Notes |
|---|--------|------|--------|-------|
| 1 | Markdown | MD | OPP internal | YAML frontmatter, optional base64 images |
| 2 | XLIFF 1.2 | XLIFF | OPP internal | `<bx>/<ex>` inline tags, `<trans-unit>` per segment |
| 3 | DOCX | ORF | pandoc | Most common ORF output |
| 4 | ODT | ORF | pandoc | OpenDocument text |
| 5 | EPUB | ORF | pandoc | Reflowable book |
| 6 | RTF | ORF | pandoc | Rich text format |
| 7 | ICML | ORF | pandoc | InCopy / InDesign workflow |
| 8 | HTML | ORF | `markdown` lib | Pure-Python |
| 9 | PDF | ORF | WeasyPrint (default) | HTML→PDF, no LaTeX required |
| 10 | PPTX | ORF | python-pptx | Slides from MD structure |
| 11 | SRT | ORF | internal | SubRip subtitle format |
| 12 | CSV | ORF | pandas | Tabular round-trip |
| 13 | XLSX | ORF | openpyxl | Sheets from tables |
| 14 | IPYNB | ORF | nbformat | Notebooks from MD cells |
| 15 | EML/MSG | ORF | stdlib email | Email round-trip (MSG requires Aspose) |

PDF XLIFF is intentionally blocked at the OPP level — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#5-pdf--xliff-blocked).

---

## 6. Configuration sources

OPP merges configuration from (in order of precedence, highest first):

1. CLI flags (`--source-lang`, `--ocr-engine`, etc.)
2. `--config` YAML file (`config/default.yaml` in repo root or CWD; legacy `opp_config.yaml` also accepted with deprecation warning)
3. Environment variables (`OPP_OCR_ENGINE`, `OMNI_CACHE_DIR`, ...)
4. Built-in defaults

The MCP server adds:

5. `OPP_MCP_ALLOWED_DIRS`, `OPP_MCP_MAX_FILE_SIZE`, `OPP_MCP_TIMEOUT`, `OPP_MCP_HOST`, `OPP_MCP_PORT`
6. `MCP_SHARED_SECRET` (if set, enables auth)

`MCPConfig` is loaded at server import time, so env vars must be set before `python -m opp.mcp.server` starts. Setting them inside a tool call is too late.

---

## 7. Where to look in the source

| Concern | File |
|---------|------|
| Magic-bytes detection | `src/opp/detector.py` |
| Pipeline orchestrator | `src/opp/pipeline.py` |
| Each format's extractor | `src/opp/extractors/<fmt>.py` |
| Markdown output | `src/opp/markdown/generator.py` |
| XLIFF output | `src/opp/xliff/` |
| Resource dedup | `src/opp/resource_manager.py` |
| Skeleton preservation | `src/opp/pipeline.py:save_skeleton` |
| CLI entry point | `src/opp/cli.py` |
| MCP server | `src/opp/mcp/server.py` |
| Path security | `src/opp/mcp/security.py` |
| Auth | `src/opp/mcp/auth.py` |
| Rate limiting | `src/opp/mcp/rate_limiter.py` |
| Error codes | `src/opp/mcp/_errors.py` |
| Cache | `src/opp/utils/cache.py` (used by `cli.py`) |
