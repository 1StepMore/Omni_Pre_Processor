# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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