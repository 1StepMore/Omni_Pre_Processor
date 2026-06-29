# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **`fix(pyproject.toml)`: pin `faster-whisper` upper bound** — was unpinned (`"faster-whisper"`), now `>=1.0.0,<2.0.0`. **Important note**: `ctranslate2` (a faster-whisper core dependency) does not publish Python 3.13 wheels as of 2026-06. Users on Python 3.13 may need to build `ctranslate2` from source or use the `[audio]` extra on Python 3.12. The OPP CLI and other components are unaffected — this only blocks the `[audio]` optional extra.

### Added

- **feat(src/opp/cli.py)**: opt-in `.env` auto-loading (`env-autoload`) via `--load-dotenv` flag and `OPP_AUTOLOAD_DOTENV=1` env var. Search path: `$OPP_DOTENV` → `./.env` → walk parents → `~/.config/opp/.env`. Mirrors OL's existing `_load_dotenv` pattern (no python-dotenv dependency).
- **`tests/test_env_autoload.py`** — comprehensive tests for `_load_dotenv_for_opp()` (135 lines): covers empty file, comments-only, simple KEY=value, double-quoted values, single-quoted values, malformed line tolerance. Verifies the `setdefault` precedence (shell env wins over .env file).
- **`test(tests/test_structure_html_tags.py)`**: new test class `TestStructureHtmlTags` covering bare HTML tags, tags with attributes (OPP#36 regression guard), and content tags. Locks in the regex fix from commit 21e890d. 28 parametrized test cases. (Resolves OPP#41)

### Fixed

- **fix(.env.example, config/default.yaml, opp_config.yaml, src/opp/cli.py, docs/ARCHITECTURE.md, docs/API.md, AGENTS.md, README.md)**: Update stale `opp_config.yaml` references to `config/default.yaml`; add Python 3.13 prerequisite; expand `.env.example` with 20+ MCP/observability vars; remove dead `OPP_RESOURCE_STORAGE_DIR` and `# pdf: complex` comment; correct MCP tool count 5→7 (add `save_skeleton`, `ping`).
- **HTMLExtractor strips structural HTML tags** (`src/opp/extractors/html.py`): added regex (`_STRUCTURE_HTML_TAGS`) and helper (`_strip_structural_html_tags()`) to remove bare lines like `<html>`, `</body>`, `<!doctype html>` that were leaking as visible text in markdown output. Called in the markdown conversion path after `_fix_tables()`.
- **`_load_dotenv_for_opp()` handles `export KEY=val` prefix** (`src/opp/cli.py`): added `line.removeprefix("export ").lstrip()` before partition. Previously `export FOO=bar` would set `export FOO` instead of `FOO`.
- **OPP#36 — `_STRUCTURE_HTML_TAGS` regex now strips tags with attributes** (`src/opp/extractors/html/markdown_converter.py:45-48`): the original regex required `>` immediately after the tag name, so `<html lang="en">` and `<body bgcolor="">` slipped through. Added `(?:\s[^>]*)?` to match optional attributes. Tests extended in `tests/test_html_extractor_split.py::test_strip_structural_html_tags_with_attributes` (single-attr, multi-attr, doctype, uppercase, unquoted) and a new end-to-end guard `tests/test_html_extractor.py::test_opp36_no_leaking_html_tags_with_attributes`.
- **`fix(src/opp/commands/extract.py)`**: skeleton.html now written for `--target-format both` (was only for `== "html"`, silently dropped when using `both`). One-line fix bringing the skeleton-write check into alignment with the PDF→HTML routing at line 72. (Resolves OPP#40)
- **`feat(src/opp/extractors/epub.py)`**: `EPUBExtractor.extract()` now sets `skeleton=result_bytes` and `skeleton_files=[(chapter_path, modified_bytes)]` in `ExtractionResult`. The new `_build_epub_skeleton_with_segment_ids()` method injects `data-trans-unit-id="N"` attributes into EPUB chapter XHTML elements (1-indexed numeric IDs matching XLIFF generator's `str(idx + 1)` format). This enables ORF's xliff2epub channel to match translated segments back to original elements (previously 0/N translations were applied because the EPUB had no segment identifiers). (Resolves OPP#39 OPP side)
- **`feat(src/opp/commands/extract.py)`**: added JSON-specific override that uses `JSONExtractor.extract_key_values()` + `KeyValueChannel.convert()` to produce proper XLIFF for JSON inputs when `--target-format` is `xlf` or `both`. This closes the loop on the JSON XLIFF pipeline: OPP → XLIFF → OL → ORF → JSON. The override is placed before manifest computation so the XLIFF file is correct for unit counting. (Resolves OPP#42 OPP side)

### Documentation

- **docs(ARCHITECTURE.md)**: Add cross-reference to suite-level `ARCHITECTURE.md`.

## [0.8.0] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.0` but release notes were not retroactively written.

## [0.8.1] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.1` but release notes were not retroactively written.

## [0.8.2] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.2` but release notes were not retroactively written.

## [0.8.3] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.3` but release notes were not retroactively written.

## [0.8.4] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.4` but release notes were not retroactively written.

## [0.8.5] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.8.5` but release notes were not retroactively written.

## [0.9.0] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.9.0` but release notes were not retroactively written.

## [0.9.1] - 2026-06-XX

### Unknown

- Version bumped in `pyproject.toml` to `0.9.1` but release notes were not retroactively written.

## [0.7.3] - 2026-06-25

### Added

- **OPP#10 — MCP server cleans up on shutdown** (`src/opp/mcp/server.py`). The server now registers an `atexit` handler and SIGTERM/SIGINT handlers that:
  1. Always unlinks all internal temp files (prefix `opp_mcp_`, created by `_safe_temp_output`)
  2. Conditionally removes the entire `resource_storage_dir` if the new `OPP_MCP_CLEANUP_ON_SHUTDOWN=true` is set (default `false` for backward compat — the resource dir is user-facing by default).

Fixes disk leak in long-running MCP server deployments.

### Security

- The `cleanup_on_shutdown` rmtree path includes a safety guard: if `resource_storage_dir` resolves to `/` or the current working directory, the cleanup is refused (logged as error). Prevents accidental data loss from a misconfigured path.

## [0.7.2] - 2026-06-25

### Fixed

- **Issue #9 — PDF OCR language hardcoded to English** (`src/opp/extractors/pdf.py:287`). Tesseract OCR was always called with `lang="eng"`, preventing OCR of non-English PDFs/images. Fixed by reading the new `OPP_OCR_LANG` env var (defaults to `eng` for backward compat). Supports any tesseract language code (`chi_sim`, `jpn`, `fra`, etc.).

## [0.7.0] - 2026-06-24

### Changed
- **JSONExtractor**: `extract()` now emits BOTH a ` ```json ` fenced block (full original JSON, preserves structure) AND `json_field:path = value` lines (one per string value, for OL translation). This allows string values to be translated while preserving numbers, booleans, nulls, key order, and array indices. See `test_json_extractor.py::TestJSONExtractorTranslations` and `TestJSONExtractorRoundTrip` for new test coverage.

### Migration
- ORF 0.4.7+ is required to fully consume the new format. The ORF `md2json` channel now has a combined mode that uses the fenced block as base structure and applies `json_field:` translations on top of string values.
- The `extract_key_values()` method (used by XLIFF channel) is unchanged.

## [0.6.7] - 2026-06-24

### Fixed
- **Issue #7 — PDF text run extraction loses spaces** (`src/opp/extractors/pdf.py:extract_text_blocks`):
  `page.get_text("blocks")` joins text from multiple text runs (justified text, separate
  `insert_text` calls at the same y coordinate) with `\n` instead of space. This produced
  garbled output like `"Hello\nPDF"` which LLMs cannot translate correctly. Fix: when a
  text block (`block_type == 0`) contains `\n`, fetch word-level data via
  `page.get_text("words", clip=bbox)` and reconstruct per-line text with spaces between
  words. Block-level structure (which handles multi-column layouts) is preserved — word
  extraction is only used WITHIN a block's clip region, not page-wide. New
  `_reconstruct_text_from_words()` helper handles the word-to-text recombination.
  Regression: the Issue #5 OCR fallback still triggers correctly on image-only PDFs
  (text-layer still sparse after reconstruction).

## [0.6.6] - 2026-06-24

### Fixed
- **Issue #5 — PDF Extractor returned 0 chars for image-only / scanned PDFs** (`src/opp/extractors/pdf.py:extract_text_blocks`): All 12 PDF cells in the 2026-06-24 200-cell matrix regression failed because `fitz.Document.get_text("blocks")` returns an empty list for pages that are entirely rasterized images (scanned PDFs, image-only PDFs, etc.). The OPP extractor was silently emitting 0 paragraphs even when the visible content of the page was substantial — just encoded as an image instead of as a text layer. Fix: detect per-page text-layer sparsity and run OCR on the full page as a fallback. New `PDFExtractor.OCR_FALLBACK_TEXT_THRESHOLD = 30` (calibrated empirically: 16-char title metadata triggers OCR, 100+ char text-layer page does not). When `page.get_text("blocks")` returns < 30 chars, the page is rendered as a 200-DPI image via `page.get_pixmap()` and the existing `_ocr_tesseract` / `_ocr_rapidocr` helpers (same infrastructure already used by the image-extraction path for inline images) are invoked on the full page. OCR results are returned as `TextBlockData` with the full page bbox, then integrated into `extraction_result.paragraphs` like any other text block. Silent no-op when neither Tesseract nor RapidOCR is installed — the text-layer path still runs and emits whatever it could extract (typically just title metadata for these PDFs); no crash, no silent data loss. Reuses existing OCR deps (`[ocr]` extra + optional Tesseract binary) — no new package requirements. Patch bump per `docs/API_STABILITY.md` § 2.1: backward-compatible behavior change, output is strictly more complete than before, no public-surface change. Verified empirically: a test PDF rasterized from "Technical Report: A comprehensive overview" returned 0 paragraphs with the old code, and now correctly attempts OCR on the rendered page (chars emitted depend on whether Tesseract / RapidOCR is installed locally — `pytesseract` + `tesseract` binary is the typical CI/dev install). 7 new unit tests in `tests/test_pdf_extractor.py::TestPDFOCRFallback` pin the contract: text-layer PDF doesn't trigger OCR, empty/short-text pages do, OCR results integrate into paragraphs, real image-only PDF uses the fallback path, threshold constant is pinned, PIL-missing is a silent no-op.

## [0.6.5] - 2026-06-24

### Fixed
- **`all` extra self-referential typo** (`pyproject.toml:75`): the `all` extra listed `"omni-pre-processor[audio,notebook,office,web,email,ocr,mcp,youtube]"` — OPP (renamed from `opp` to `omni-pre-processor` in 0.6.1) declaring itself with its own extras. This was always broken (circular self-dep) but became externally visible after the rename: when uv ran from any sibling project that walked up to the suite workspace, it saw OPP required from TWO sources — (1) the suite's `tool.uv.sources.omni-pre-processor = { path = "Omni_Pre_Processor" }` and (2) OPP's own `[all]` extra — both pointing at the same `file:///.../Omni_Pre_Processor` URL. Result: `uv sync` failed with `Requirements contain conflicting URLs for package omni-pre-processor in split python_full_version >= '3.15' and sys_platform == 'win32'`. Fix: changed the literal `omni-pre-processor` to `markitdown` (the package whose `youtube` extra on line 60 actually pulls in `markitdown[youtube-transcription]`). The `all` extra now pulls `markitdown[audio,notebook,office,web,email,ocr,mcp,youtube]` — note that markitdown 0.1.6 doesn't have all those named extras (it warns and silently skips the unknown ones) so the `all` extra in practice adds the markitdown install without a specific markitdown extras; cleaning up the markitdown extras list to use the real ones (`docx,xlsx,pdf,pptx,youtube-transcription,image,all`) is a separate polish item for 0.6.6. Patch bump per docs/API_STABILITY.md § 2.1: backward-compatible packaging fix, no public-surface change. Affected: every sibling submodule (`Omni_Localizer`, `Omni_Re_Formatter`, and the suite root) whose `uv sync`/`make install` was previously failing with the OPP URL conflict; verified that the dep graph now resolves cleanly (296 packages in 19ms) and the suite's `verify_usability.py` continues to report all 5 groups ✅.

## [0.6.4] - 2026-06-24

### Fixed
- **E2E-81** (`src/opp/extractors/csv.py`, `src/opp/markdown/generator.py`): CSV cells with quoted multi-line values (common in spreadsheet exports) were silently collapsed to single spaces in the rendered markdown table. `pd.read_csv(on_bad_lines="skip")` dropped any mis-parsed row, and `MarkdownGenerator._escape_table_cell` did `cell.replace('|', '\\|').replace('\n', ' ')` which collapsed every embedded newline to one space. Two fixes: switched `on_bad_lines="skip"` → `"warn"` so mis-parses surface as warnings (no longer silent), and `_escape_table_cell` now escapes newlines as `<br>` (which pandoc tables render as a soft line break) and collapses surrounding whitespace.
- **E2E-82** (`src/opp/extractors/html.py:122-137, 215-227`): `HTMLExtractor.extract()` called docling via `_extract_with_docling` which returned `""` on any failure (exception or empty result) and logged at DEBUG level only. The two docling call sites were asymmetric: complex mode + docling NOT installed fell back to readability correctly, but complex mode + docling installed-but-fails silently used empty content, and simple mode → readability → if low quality → try docling had the same silent-empty-failure. User-visible symptom: a 10MB HTML page where docling times out or OOMs produced a 0-character `.md` with a misleading "使用docling(AI)提取HTML" success warning. Fix: both docling call sites now wrap the call in try/except, check the returned text is non-empty, and fall back to readability with a clear "docling失败 ... 降级到readability" warning.

## [0.6.1] - 2026-06-12

### Changed
- **`Optional[X]` → `X | None` migration**: All 108 `Optional[X]` usage converted to Python 3.12+ union syntax across OPP codebase (ruff UP045/UP006/UP035).
- **pyright 4/5 checks re-enabled**: `reportMissingTypeStubs`, `reportDeprecated`, `reportUnusedVariable`, `reportUnusedImport` now active. `reportMissingParameterType` remains suppressed (35+ annotation gaps).

### Fixed
- **`print()` → `logger.warning()`** in `opp/cli.py:536` for file-skip reporting.
- **Unused imports and dead code** cleaned across `extractors/html.py`, `markdown/generator.py`, `config/__init__.py`, `opp_hermes/opp_tool.py`.

## [0.6.0] - 2026-06-03

### Added
- **Floating DOCX image support** — OPP now distinguishes `wp:anchor` (floating) from `wp:inline` drawings, exposing anchor coordinates for downstream ORF wp:anchor reinjection.
  - `ImageData.is_floating: bool = False` — True for `wp:anchor` drawings, False for `wp:inline`
  - `ImageData.wp_anchor_h: int = 0` — horizontal position offset in EMU units (read from `wp:posOffset` inside `wp:positionH`)
  - `ImageData.wp_anchor_v: int = 0` — vertical position offset in EMU units (read from `wp:posOffset` inside `wp:positionV`)
  - `docx._extract_anchor_offsets(drawing, WP_NS, ns_map)` — module-level helper that returns `(h, v)` EMU tuple; returns `(0, 0)` for inline drawings, `wp:align`-only anchors, and malformed/missing `posOffset` text
  - `images.json` now emits `is_floating: true` and `wp_anchor_h` / `wp_anchor_v` keys for floating images; zero-valued offsets are omitted from the JSON to keep the inline-image shape unchanged
- **pytest markers** — `conftest.py` registers `e2e` and `real_chain` markers used by the new Phase 2 nightly-test suite
- **Phase 2 test coverage** — two new test files
  - `tests/test_opp_floating_image_fix.py` — unit tests for `_extract_anchor_offsets` (inline, posOffset, wp:align, missing children, non-numeric text, partial anchor), `ImageData` defaults/backward-compat, and `images_json` floating-field propagation
  - `tests/test_opp_ol_orf_contracts_md.py` — end-to-end OPP→OL→ORF MD-path contract tests with a comprehensive translate mock, asserting the public `MD2DOCXConverter.convert()` consumes real OPP output

### Changed
- **`_extract_inline_drawings` (docx.py)** — sets `paragraph_index=None` for floating drawings (they are not anchored to a `w:p`) and populates the new `is_floating` / `wp_anchor_h` / `wp_anchor_v` fields from the `wp:anchor` element when present

### Notes
- This unblocks real-LLM nightly tests (`tests/test_e2e_real_llm.py` in Omni_Re_Formatter) that need floating-image metadata to inject `wp:anchor` elements into the regenerated DOCX.
- The current Haier DOCX test fixture contains 0 floating images; the floating-image path is exercised by synthetic XML in `test_opp_floating_image_fix.py` until a real fixture is added.

## [0.5.9] - 2026-05-28

### Fixed
- **OPP image copying bug (E2E-02)**: Fixed `MarkdownGenerator.generate()` to write all images, not just those with matching paragraph_index
  - Problem: `orphaned` filter only caught images with ALL position fields as `None`
  - Images with `paragraph_index` outside paragraph range (e.g., indices 9,13,18,20,24 vs paragraphs 0-8) were lost
  - Fix: track written images by `id()` and mark all non-written as orphaned
  - Result: All 24 extracted images now written to output instead of only 2

### Added
- **`images.json` generation**: `OPPPipeline.generate_images_json()` method generates `images.json` file containing image placement data (paragraph_index, page_number, slide_index, element_index, spine_index, mime_type, width, height)
- **MCP `output_dir` config**: `MCPConfig` now accepts optional `output_dir: Path` field for persistent file output
- **`output_formats=["json"]`**: `extract_document` and `batch_extract` accept `"json"` in output_formats to generate `images.json`

### Changed
- **`images_json_path` in response**: When `images.json` is generated, response now includes `images_json_path` field with the file path

### Documentation
- **`add_image()` docstring**: Documented UUID-based filename generation and `_mapping` tracking
- **`generate_to_file()` docstring**: Documented image file naming pattern `{stem}_image_{seq}.{ext}`

## [0.5.7] - 2026-05-27

### Fixed
- **markdown.py image externalization**: `generate()` and `generate_to_file()` now use `images_dir` parameter to write images to `{stem}_images/` and reference them as `./{stem}_images/{stem}_image_N.png` instead of base64 inline data URIs

## [0.5.5] - 2026-05-27

### Fixed
- **MD image externalization**: `generate_to_file()` now writes images to `images/` directory and uses `![](./images/N.png)` references instead of base64 data URIs. Improves Pandoc compatibility and prevents image loss during MD→DOCX conversion.
- **DOCX orphaned images**: `_extract_inline_drawings()` now assigns virtual paragraph_index to images without valid paragraph context, eliminating orphaned images.

## [0.5.4] - 2026-05-27

### Fixed
- **XLIFF 1.2 namespace**: Post-process xliff output to upgrade namespace from 1.1 to 1.2 (translate-toolkit outputs 1.1, ORF requires 1.2)

## [0.5.3] - 2026-05-27

### Fixed
- **MCP serializer field name**: `images[].data` → `images[].data_base64` to align with ORF ImagePlacement schema

## [0.5.2] - 2026-05-27

### Fixed
- **asyncio test compatibility**: Use `asyncio.run()` instead of deprecated `get_event_loop().run_until_complete()` for Python 3.12+ compatibility

## [0.5.0] - 2026-05-27

### Fixed
- **DOCX image extraction Bug**: `rel.target_ref` → `rel.reltype` in image relationship check. The `target_ref` contains file paths like `media/rId20.jfif` which never contain "image", while `reltype` contains the OOXML relationship type URI that does include "image".
- **DOCX duplicate image extraction**: Removed redundant first loop in `extract_images()` that only extracted images without position context; all DOCX images now go through `_extract_inline_drawings()` which correctly sets `paragraph_index`.

### Added
- **Multi-format image position fields**: `ImageData` now supports format-specific position tracking:
  - `paragraph_index: Optional[int]` — DOCX inline drawings (0-based)
  - `page_number: Optional[int]` — PDF pages (1-based)
  - `slide_index: Optional[int]` — PPTX slides (0-based)
  - `element_index: Optional[int]` — HTML DOM elements (0-based)
  - `spine_index: Optional[int]` — EPUB spine order (0-based)
- **PPTX image position**: `extract_images()` now populates `slide_index` for each image
- **PDF image position**: `extract_images()` now populates `page_number` (1-based) for each image
- **HTML image position**: `_extract_images()` now populates `element_index` for each `<img>` element
- **EPUB image position**: `_extract_images()` now populates `spine_index` for each image
- **MarkdownGenerator fallback selection**: Position key selection now falls through `paragraph_index` → `page_number` → `slide_index` → `element_index` → `spine_index`
- **Orphaned image detection**: `orphaned` images now defined as images with ALL position fields as `None`
- **MCP serializer**: `_serialize_image()` now outputs all 5 position fields in manifest

### Changed
- **ImageData dataclass**: Extended with 4 new optional position fields; existing `paragraph_index` field retained for DOCX inline drawings

### Deprecated
- **DOCX rels-only image extraction**: First loop in `extract_images()` removed; use `_extract_inline_drawings()` directly for position-aware extraction

## [0.4.3] - 2026-05-26

### Fixed
- **Image paragraph positioning**: Added `ImageData.paragraph_index` field; `_extract_inline_drawings()` now uses lxml parent axis to track which `result.paragraphs` index each image belongs to, and `MarkdownGenerator.generate()` interleaves images immediately after their host paragraphs instead of dumping all images at a separate `## Images` section

## [0.4.2] - 2026-05-26

### Fixed
- **MarkdownGenerator image injection**: `generate()` now emits `![Image N](data:mime;base64,...)` data URI references for all images in `ExtractionResult.images`, making markdown self-contained for MCP transport
- **MCP image metadata**: `generate_markdown`, `extract_document`, and `batch_extract` tools now return `images_dir` field pointing to the `{stem}_images/` directory for downstream ORF tooling
- **Image file extension**: `generate_to_file()` now uses correct mime-type-derived extension instead of hardcoded `.png`

## [0.4.1] - 2026-05-26

### Fixed
- **DOCX image extraction**: `extract_images()` now parses `word/document.xml` via zipfile+lxml to extract inline `w:drawing` elements (previously only used `doc.part.rels`); 72 images extracted from test docx (was 0)
- **Chinese-numbered heading detection**: Added heuristic regex patterns to detect Chinese section markers (`一、`、`二、`、`三、` etc.) and assign proper markdown heading levels (`##` for section headings, `###` for subsections)
- **Table position interleaving**: Added `position` field to `TableData` and `ParagraphData` dataclasses; `MarkdownGenerator.generate()` now merges tables with paragraphs by source position instead of appending all tables at end

## [0.4.0] - 2026-05-25

### Fixed
- **MCP `extract_document`**: `_serialize_paragraph()` now includes `chapter` and `page` fields from `ParagraphData`; previously these were silently dropped and agents could not determine paragraph origin
- **MarkdownGenerator**: Emit `<!-- chapter: {chapter} -->` HTML comment before headings that have a `chapter` value, enabling chapter-aware downstream processing

### Added
- **Chapter-aware metadata** — ParagraphData now carries `chapter` field for EPUB spine order and PDF page-based chapter mapping
  - `ParagraphData.chapter: Optional[str]` — chapter name from EPUB spine item title or PDF TOC
  - `ParagraphData.page: Optional[int]` — page number for PDF paragraph-to-chapter mapping
  - `DocumentMetadata.source_md5: Optional[str]` — source file MD5 for cache invalidation
  - `EPUBExtractor._extract_chapters()` — fills chapter field from spine item title/name
  - `PDFExtractor._build_chapter_paragraph_map()` — maps paragraphs to chapters by page number

- **Chunk structure definition** — Standardized chunk metadata interface for Pipeline/OLL
  - `src/opp/chunker.py` — `Chunk` and `ChunkedResult` dataclasses
  - `ChunkMetaBuilder.build()` — groups paragraphs by chapter, computes character offsets
  - No splitting logic — OPP defines structure only, Pipeline/OLL decides boundaries
  - `tests/test_chunker.py` — 5 test cases for ChunkMetaBuilder

### Changed
- **Core principle**: OPP only defines structure ("是什么"), never makes splitting decisions ("怎么做")

## [0.3.0] - 2026-05-23

### Added
- **Inline formatting tracking** — Bold, italic, underline, strikethrough preserved in XLIFF as `<bx>`/`<ex>` tags for downstream formatting restoration
  - `extract_runs()` methods added to DOCX, PPTX, EPUB, HTML extractors
  - XLIFF generator now preserves `<bx>`/`<ex>` tags as XML (not escaped) via DOM manipulation to bypass translate-toolkit escaping
  - 53 unit/integration tests for inline formatting extraction and XLIFF generation

### Fixed
- **Concurrency**: Add `threading.Lock` to `OPPConfig` singleton with double-checked locking
- **Resource Manager**: Add `RLock` to protect `_mapping` and `_cross_ref` dicts under concurrent access
- **MCP Config**: Add `logger.warning()` for silent YAML load failures
- **MCP `output_formats`**: Accept both string and list for ergonomic API (e.g., `"md"` or `["md"]`)
- **MCP `generate_xliff`/`generate_markdown`**: Output path validation now works for non-existent files (previously required file to exist)
- **MCP `xliff_units_count`**: Count `<trans-unit` elements instead of `<target>` (source XLIFF has no target elements)
- **EPUB `extract_runs`**: Handle NavigableString plain text children (was only processing element nodes, discarding plain text fragments between formatted elements)
- **DOCX/PPTX**: Replace swallowed exceptions with `logger.warning()` in inline formatting extraction
- **PDF**: Wrap `extract()` body in try/finally to ensure `doc.close()` on all exit paths
- **Email**: Use `tempfile.mkstemp()` for atomic temp file creation (TOCTOU race fix)
- **HTML**: Pre-compile 8+ regex patterns at module level (25 JS indicators) to avoid per-call recompilation
- **Tests**: Add missing `import sys` in `test_docx_e2e.py`

### Security
- **TOCTOU**: Atomic temp file creation via `mkstemp()` in email extraction

### Performance
- **HTML**: Pre-compiled regex patterns eliminate per-call compilation overhead

## [0.2.1] - 2026-05-22

### Fixed
- **Build**: Fix sdist path from absolute `/src/opp` to relative `src/opp`
- **Windows**: Replace `posixpath` import with `os.path` for cross-platform compatibility
- **CLI**: Add file existence validation in `expand_directories()` to skip non-existent paths
- **CLI**: Add try/catch for permission errors when reading file stats and computing MD5
- **CLI**: Use `logger.exception()` instead of `logger.error()` for better stack traces
- **Docs**: Fix `OPP_ALLOWED_DIRECTORIES` to `OPP_MCP_ALLOWED_DIRS` in README
- **Docs**: Fix typo in README (` stdio` → `stdio`)

### Dependencies
- **MCP extra**: Add `fastmcp` dependency
- **MCP extra**: Add `pyyaml` dependency
- **Audio extra**: Add `torch` dependency for GPU detection

## [0.2.0] - 2026-05-19

### Added
- **Manifest generation** - JSON manifest with source info, extraction stats, and image data
- **Skeleton preservation** - Original DOCX/PPTX ZIP structure preserved for downstream XLIFF→DOCX/PPTX backfill
  - Captures OOXML skeleton ZIP for DOCX and PPTX
  - `save_skeleton()` method added to OPPPipeline
  - `skeleton` and `skeleton_files` fields added to ExtractionResult

### Features
- Manifest.json generation with source file info, extraction outputs, and resource data
- Skeleton.zip creation for DOCX/PPTX formats preserving key XML files

### Tests
- `test_manifest_generation.py` - 6 tests for manifest generation
- `test_skeleton_preservation.py` - 6 tests for skeleton preservation

## [0.1.0] - 2024-05-19

### Added
- **MCP Server** - New agent-facing Model Context Protocol server
  - `extract_document` tool for single file extraction
  - `batch_extract` tool for processing multiple files
  - `detect_format` tool for format detection
  - `generate_markdown` tool for MD output
  - `generate_xliff` tool for XLIFF translation format
  - Path validation with directory allowlist
  - File size limits (100MB default)
  - Security: blocks path traversal, symlinks, system directories, executables

- **OpenCode Skill** (`src/opp_agent/`)
  - SKILL.md for OpenCode agent integration

- **Hermes Plugin** (`src/opp_hermes/`)
  - Plugin package for Hermes agent integration
  - `opp_extract` tool registration

### Features
- Document extraction: DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG
- Image OCR with Tesseract and RapidOCR
- Email extraction with attachment recursion
- Audio/Video transcription with Whisper
- Format auto-detection via magic bytes
- Markdown and XLIFF 1.2/2.0 output
- Resource management with MD5 deduplication

### Installation
```bash
# Core package
pip install opp

# With all features
pip install opp[all]

# With MCP server (for agents)
pip install opp[mcp]
```

### CLI Usage
```bash
# Extract to Markdown
opp --target-format=md document.docx

# Generate XLIFF for translation
opp --target-format=xlf --source-lang=en --target-lang=zh document.docx

# Batch processing
opp --batch folder/
```

### Documentation
- `docs/hermes-integration.md` - Hermes integration guide
- `docs/hermes-mcp-config.yaml` - MCP server configuration
- `docs/opencode-installation.md` - OpenCode skill installation
- `docs/hermes-plugin-installation.md` - Hermes plugin installation

### Scripts
- `install_opp_agents.sh` - Install for both OpenCode and Hermes (Unix)
- `install_opp_agents.bat` - Install for both OpenCode and Hermes (Windows)
## [0.6.2] - 2026-06-23

### Fixed

- **Orphaned image double-embedding (E2E-15)**: `MarkdownGenerator.generate()` now filters orphaned images whose `_seq` was already output inline, preventing Pandoc from embedding the same image twice.
  - `src/opp/markdown/generator.py`

## [0.6.3] - 2026-06-23

### Fixed

- **Verbose mode stderr output (CLI bug fix)**: `opp -v` was file-only logging — the "Detected: docx" message went to `logs/opp_TIMESTAMP.log` but not to stderr. `setup_logger(verbose=True)` now also attaches a `StreamHandler(sys.stderr)` with a human-readable formatter. File-based observability preserved unchanged.
  - Fixes `tests/test_cli_smoke.py::TestFlags::test_detect_format_flag` (was failing since the `print -> logger` migration in 24f8fd0).
  - Usage: `opp --detect-format -v file.docx` now shows `[INFO]   Detected: docx (confidence: 1.0)` in the terminal.
  - `opp` without `-v` stays quiet on stderr (0 bytes); log file unchanged.
  - `OMNI_LOG_FORMAT=json` still produces JSON in the log file; stderr stays human-readable.
