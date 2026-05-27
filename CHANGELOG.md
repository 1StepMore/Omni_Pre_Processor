# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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