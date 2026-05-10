# Phase 4 Plan: 用户体验+OPP→OL端到端集成+PyPI发布

## TL;DR

> **Quick Summary**: Complete OPP by integrating the existing but disconnected Markdown/XLIFF generators into the pipeline and CLI, add end-to-end tests for all three formats plus OPP→OL integration, and prepare for PyPI publishing.
>
> **Deliverables**:
> - `src/opp/cli.py` - Enhanced CLI with --target-format, --source-lang, --target-lang
> - `src/opp/pipeline.py` - Extended with MD/XLIFF output generation
> - `tests/test_docx_e2e.py` - DOCX E2E tests (MD + XLIFF output)
> - `tests/test_pptx_e2e.py` - PPTX E2E tests (MD + XLIFF output)
> - `tests/test_pdf_e2e.py` - PDF E2E tests (MD + XLIFF output)
> - `tests/test_opp_ol_integration.py` - OPP→OL integration (mock/stub OL)
> - `.github/workflows/publish.yml` - PyPI publishing workflow
> - Version sync fix (hatchling dynamic versioning)
>
> **Estimated Effort**: 1 day
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: CLI enhancement → Pipeline integration → E2E tests → PyPI setup

---

## Context

### Original Request
Implement Phase 4 of OPP as specified in OPP_DD_Vibe_Phase版.md - User experience enhancement + OPP→OL end-to-end integration + PyPI publishing

### Phase 4 Overview
- **Goal**: Complete the feature set by integrating existing generators into pipeline + CLI, add comprehensive E2E tests, prepare for PyPI publishing
- **Prerequisites**: Phase 0-3 all complete
- **Dependencies**: Phase 1 (MarkdownGenerator), Phase 2 (XLIFFFileGenerator), Phase 3 (OPPPipeline)

### What's Already Defined (from Phase spec)
- UTDD test deliverables: test_docx_e2e.py, test_pptx_e2e.py, test_pdf_e2e.py, test_opp_ol_integration.py
- ATDD acceptance criteria: 100% E2E pass rate, seamless OPP→OL integration, one-click PyPI install
- BDD scenario: Full localization pipeline with OPP + OL

### What's Already Implemented (verified via code review)
- `src/opp/markdown.py` - MarkdownGenerator (fully implemented, generate() and generate_to_file())
- `src/opp/xliff/generator.py` - XLIFFFileGenerator (fully implemented, from_extraction_result factory)
- `src/opp/pipeline.py` - OPPPipeline with process_file() and process_batch() (Phase 3 complete)
- `src/opp/cli.py` - CLI with --detect-format, --resource-dir, --report, --batch (Phase 3 complete)
- `pyproject.toml` - Package config with name="opp", version="0.1.0", hatchling build system

### What's MISSING (Integration Gap)
1. **Pipeline**: OPPPipeline.process_file() returns ProcessingResult but NEVER calls generators
2. **CLI**: No --target-format, --source-lang, --target-lang flags
3. **PyPI**: No publishing workflow, version defined in TWO places (sync issue)

---

## Work Objectives

### Core Objective
Complete OPP feature integration by connecting existing but disconnected generators to the pipeline + CLI, add E2E tests, and prepare for PyPI publishing.

### Concrete Deliverables

1. **CLI Enhancement** (`src/opp/cli.py`)
   - Add --target-format flag (md/xlf/both)
   - Add --source-lang and --target-lang flags for XLIFF
   - Add --output-dir for controlling output location
   - Maintain backward compatibility (existing flags still work)

2. **Pipeline Extension** (`src/opp/pipeline.py`)
   - Extend OPPPipeline with generate_markdown() method
   - Extend OPPPipeline with generate_xliff() method
   - Add output path handling
   - Add result object with both MD and XLIFF content

3. **E2E Tests** (4 test files)
   - test_docx_e2e.py: DOCX → MD + XLIFF, verify content
   - test_pptx_e2e.py: PPTX → MD + XLIFF, verify content
   - test_pdf_e2e.py: PDF → MD + XLIFF, verify content
   - test_opp_ol_integration.py: Mock OL tool, test full pipeline

4. **PyPI Publishing Setup**
   - GitHub Actions workflow for PyPI publishing
   - Version sync fix (hatchling dynamic versioning)
   - TestPyPI publishing for verification

### Definition of Done
- [ ] `opp --help` shows --target-format, --source-lang, --target-lang, --output-dir
- [ ] `opp --target-format=md file.docx` outputs valid Markdown file
- [ ] `opp --target-format=xlf --source-lang=en --target-lang=zh file.docx` outputs valid XLIFF
- [ ] All 4 E2E test files pass: pytest tests/test_*_e2e.py -v
- [ ] GitHub Actions workflow publishes to TestPyPI on tag
- [ ] Version sync resolved (single source of truth)

### Must Have
- Non-breaking changes to existing Phase 0-3 behavior
- Graceful error handling for incompatible format requests
- E2E tests clean up temporary files
- Mock OL tool for integration tests (no external dependency)

### Must NOT Have
- Changes to core extractor logic (Phase 0 complete)
- Changes to generator logic (Phase 1-2 complete)
- New external dependencies beyond OL (to be mocked)
- Hardcoded credentials in GitHub Actions

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest from Phase 0)
- **Automated tests**: Tests-after (UTDD pattern from previous phases)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - CLI + Pipeline integration):
├── Task 1: CLI enhancement (--target-format, --source-lang, --target-lang, --output-dir) [quick]
├── Task 2: Pipeline extension (generate_markdown, generate_xliff methods) [unspecified-high]
├── Task 3: Version sync fix (hatchling dynamic versioning) [quick]
└── Task 4: CLI unit tests (test_cli.py) [quick]

Wave 2 (E2E Tests - all formats):
├── Task 5: test_docx_e2e.py (DOCX → MD + XLIFF) [unspecified-high]
├── Task 6: test_pptx_e2e.py (PPTX → MD + XLIFF) [unspecified-high]
├── Task 7: test_pdf_e2e.py (PDF → MD + XLIFF) [unspecified-high]
└── Task 8: test_opp_ol_integration.py (mock OL) [unspecified-high]

Wave 3 (PyPI Publishing + Final):
├── Task 9: GitHub Actions workflow for PyPI publishing [quick]
├── Task 10: TestPyPI publishing verification [quick]
└── Task 11: Final verification + cleanup [unspecified-high]

Critical Path: T1 → T2 → T5 → T11
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Wave 1), 4 (Wave 2), 3 (Wave 3)
```

### Dependency Matrix

| Task | Blocks | Blocked By |
|------|--------|------------|
| T1 (CLI enhancement) | T2, T4 | None |
| T2 (Pipeline extension) | T5, T6, T7, T8 | T1 |
| T3 (Version sync) | T10 | None (independent) |
| T4 (CLI tests) | - | T1 |
| T5 (DOCX E2E) | - | T2 |
| T6 (PPTX E2E) | - | T2 |
| T7 (PDF E2E) | - | T2 |
| T8 (OPP-OL integration) | - | T2 |
| T9 (GitHub Actions) | T10 | None (independent) |
| T10 (TestPyPI verify) | T11 | T9, T3 |
| T11 (Final verification) | - | T5, T6, T7, T8, T10 |

### Agent Dispatch Summary

- **Wave 1**: **4** - T1 → `quick`, T2 → `unspecified-high`, T3 → `quick`, T4 → `quick`
- **Wave 2**: **4** - T5 → `unspecified-high`, T6 → `unspecified-high`, T7 → `unspecified-high`, T8 → `unspecified-high`
- **Wave 3**: **3** - T9 → `quick`, T10 → `quick`, T11 → `unspecified-high`

---

## TODOs

- [x] 1. **CLI Enhancement (--target-format, --source-lang, --target-lang, --output-dir)**

  **What to do**:
  - Extend `src/opp/cli.py` with new flags:
    - `--target-format`: choices=['md', 'xlf', 'both'] (default: None - just extract)
    - `--source-lang`: ISO language code for XLIFF source (default: 'en')
    - `--target-lang`: ISO language code for XLIFF target (required for xlf/both)
    - `--output-dir`: Path for output files (default: same as input directory)
  - Modify `process_file()` to call pipeline methods based on flags
  - Add validation: --target-lang required if --target-format=xlf or --target-format=both
  - Maintain backward compatibility (existing behavior when --target-format not specified)
  - Add help text examples for new flags

  **Must NOT do**:
  - Break existing --detect-format, --resource-dir, --report, --batch flags
  - Change behavior when --target-format not specified (just extract, don't generate)
  - Use ambiguous flag names (follow existing pattern)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: CLI argument parsing extension, straightforward argparse additions
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 2, Task 4
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/cli.py:create_parser()` - Existing argument parser structure
  - `src/opp/cli.py:process_file()` - Existing file processing logic

  **API/Type References** (contracts to implement against):
  - `argparse.ArgumentParser` - CLI argument handling
  - `OPPPipeline.process_file()` - Returns ProcessingResult

  **External References** (libraries and frameworks):
  - Python argparse: https://docs.python.org/3/library/argparse.html

  **WHY Each Reference Matters**:
  - cli.py: Maintain consistent patterns with existing flags (--detect-format, --resource-dir)
  - argparse: Use standard Python CLI patterns for choices, defaults, and help text

  **Acceptance Criteria**:

  - [ ] File modified: src/opp/cli.py
  - [ ] `opp --help` shows --target-format with choices [md, xlf, both]
  - [ ] `opp --help` shows --source-lang with default 'en'
  - [ ] `opp --help` shows --target-lang as required when --target-format=xlf
  - [ ] `opp --help` shows --output-dir
  - [ ] Error message when --target-format=xlf but --target-lang missing
  - [ ] Existing flags still work unchanged

  **QA Scenarios**:

  ```
  Scenario: --target-format flag appears in help
    Tool: Bash
    Preconditions: CLI installed (pip install -e .)
    Steps:
      1. Run `opp --help`
      2. Verify output contains "--target-format"
      3. Verify choices [md, xlf, both] are listed
      4. Verify --source-lang and --target-lang appear
    Expected Result: Help text includes all new flags
    Evidence: .sisyphus/evidence/task-1-cli-help.txt

  Scenario: --target-lang required for XLIFF output
    Tool: Bash
    Preconditions: CLI installed, valid DOCX file
    Steps:
      1. Run `opp --target-format=xlf --source-lang=en file.docx` (no --target-lang)
      2. Verify error message: "error: --target-lang is required when --target-format is xlf"
      3. Verify exit code is non-zero
    Expected Result: Clear error message, does not proceed
    Evidence: .sisyphus/evidence/task-1-missing-target-lang.txt
  ```

  **Evidence to Capture:**
  - [ ] Help text output showing new flags
  - [ ] Error message for missing --target-lang

  **Commit**: YES (group 1)
  - Message: `feat(cli): add --target-format, --source-lang, --target-lang flags`
  - Files: `src/opp/cli.py`
  - Pre-commit: `pytest tests/test_cli.py -v`

- [x] 2. **Pipeline Extension (generate_markdown, generate_xliff methods)**
- [x] 3. **Version Sync Fix (hatchling dynamic versioning)**
- [x] 4. **CLI Unit Tests (test_cli.py)**

  **What to do**:
  - Create `tests/test_cli.py`
  - Test new flags: --target-format, --source-lang, --target-lang, --output-dir
  - Test validation: --target-lang required for XLIFF
  - Test existing flags: --detect-format, --resource-dir, --report, --batch (regression)
  - Test error cases: unknown format, missing file, incompatible combinations
  - Use subprocess to test CLI directly (like real user)

  **Must NOT do**:
  - Test with real external files (use temp files)
  - Make network calls
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pytest test writing for CLI
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:

  **Test References** (testing patterns to follow):
  - `tests/test_integration.py` - pytest fixture patterns
  - `tests/conftest.py` - Test fixture setup

  **External References** (libraries and frameworks):
  - subprocess - CLI testing via subprocess
  - pytest - Testing framework

  **WHY Each Reference Matters**:
  - test_integration.py: Shows how to use tmp_path fixture, sample_files fixtures
  - conftest.py: Shows fixture structure for test files

  **Acceptance Criteria**:

  - [ ] File created: tests/test_cli.py
  - [ ] Tests for --target-format with md/xlf/both
  - [ ] Tests for --source-lang and --target-lang
  - [ ] Tests for --output-dir
  - [ ] Tests for validation (--target-lang required)
  - [ ] Tests for existing flag regression
  - [ ] All tests pass with `pytest tests/test_cli.py -v`

  **QA Scenarios**:

  ```
  Scenario: All CLI tests pass
    Tool: Bash
    Preconditions: cli.py modified, test_cli.py created
    Steps:
      1. Run pytest tests/test_cli.py -v
      2. Verify all tests pass
    Expected Result: 100% pass rate
    Evidence: .sisyphus/evidence/task-4-cli-tests.txt
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests passing

  **Commit**: YES (group 1)
  - Message: `feat(cli): add --target-format, --source-lang, --target-lang flags`
  - Files: `src/opp/cli.py`, `tests/test_cli.py`
  - Pre-commit: `pytest tests/test_cli.py -v`

- [x] 5. **DOCX End-to-End Tests (test_docx_e2e.py)**

  **What to do**:
  - Create `tests/test_docx_e2e.py`
  - Test DOCX → Markdown: verify heading hierarchy, lists, tables, images
  - Test DOCX → XLIFF: verify translation units match paragraphs, language attributes correct
  - Test DOCX → both: verify both outputs created, content matches
  - Test edge cases: DOCX with embedded images, tables, nested lists
  - Use sample files from conftest fixtures (sample_files_normal, sample_files_edge)

  **Must NOT do**:
  - Modify source DOCX files
  - Leave temp files behind
  - Test PPTX or PDF in this file (each format has its own test file)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: E2E testing with complex file verification, multiple output format validation
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8)
  - **Blocks**: Task 11
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_integration.py` - E2E test structure (use as primary pattern)
  - `tests/test_docx_extractor.py` - DOCX test patterns (use for format-specific content verification)

  **Test References** (testing patterns to follow):
  - `tests/conftest.py` - Fixture usage for sample_files_normal, sample_files_edge

  **WHY Each Reference Matters**:
  - test_integration.py: Shows how to test full pipeline with tmp_path fixture (PRIMARY PATTERN for E2E)
  - test_docx_extractor.py: Shows how to access DOCX-specific content (headings, tables, lists)

  **Acceptance Criteria**:

  - [ ] File created: tests/test_docx_e2e.py
  - [ ] Tests for DOCX → Markdown output (verify headings, lists, tables)
  - [ ] Tests for DOCX → XLIFF output (verify trans units, language attributes)
  - [ ] Tests for DOCX → both (verify both files created)
  - [ ] Tests for DOCX with images (verify image paths in MD)
  - [ ] All tests pass with `pytest tests/test_docx_e2e.py -v`

  **QA Scenarios**:

  ```
  Scenario: DOCX → MD preserves heading hierarchy
    Tool: Bash
    Preconditions: Normal DOCX file with H1, H2, H3 headings
    Steps:
      1. Run opp with --target-format=md on DOCX
      2. Read generated .md file
      3. Verify H1 appears as "# Heading", H2 as "## Heading", etc.
    Expected Result: Heading levels preserved exactly
    Evidence: .sisyphus/evidence/task-5-docx-md-headings.txt

  Scenario: DOCX → XLIFF creates correct trans units
    Tool: Bash
    Preconditions: DOCX with 5 paragraphs
    Steps:
      1. Run opp with --target-format=xlf --source-lang=en --target-lang=zh
      2. Parse generated .xlf file
      3. Verify exactly 5 <trans-unit> elements
      4. Verify source language is "en"
      5. Verify target language is "zh"
    Expected Result: One trans-unit per paragraph, correct language codes
    Evidence: .sisyphus/evidence/task-5-docx-xliff-units.txt
  ```

**Evidence to Capture:**
  - [ ] DOCX MD output with headings
  - [ ] XLIFF output with trans units

  **Commit**: YES (group 4)
  - Message: `test(e2e): add DOCX end-to-end tests`
  - Files: `tests/test_docx_e2e.py`
  - Pre-commit: `pytest tests/test_docx_e2e.py -v`

- [x] 5b. **DOCX E2E - Table preservation test**
  **Scenario**: DOCX with table → MD preserves table structure
    Tool: Bash
    Preconditions: DOCX with 3-column, 5-row table
    Steps:
      1. Run opp --target-format=md on DOCX with table
      2. Read generated .md file
      3. Verify table syntax: | Header1 | Header2 | Header3 |
      4. Verify separator row: | --- | --- | --- |
      5. Verify 5 data rows
    Expected Result: Markdown table with correct structure
    Evidence: .sisyphus/evidence/task-5b-docx-table.txt

- [x] 5c. **DOCX E2E - Image path test**
  **Scenario**: DOCX with embedded image → MD references image correctly
    Tool: Bash
    Preconditions: DOCX with one embedded image
    Steps:
      1. Run opp --target-format=md --output-dir=/tmp/test_docx on DOCX with image
      2. Verify .md file created
      3. Verify image stored in /tmp/test_docx_sample_images/ directory
      4. Verify .md contains ![](sample_images/xxx.png) reference
    Expected Result: Image extracted, path in MD correct
    Evidence: .sisyphus/evidence/task-5c-docx-image-path.txt

- [x] 5d. **DOCX E2E - XLIFF validation test**
  **Scenario**: DOCX XLIFF validates against schema
    Tool: Bash
    Preconditions: Generated sample.xlf
    Steps:
      1. Run opp --target-format=xlf --source-lang=en --target-lang=ja sample.docx
      2. Validate XLIFF with xmllint --schema xsi.xsd or similar
      3. Verify no schema errors
    Expected Result: Valid XLIFF 1.2 format
    Evidence: .sisyphus/evidence/task-5d-docx-xliff-valid.txt

- [x] 6. **PPTX End-to-End Tests (test_pptx_e2e.py)**

  **What to do**:
  - Create `tests/test_pptx_e2e.py`
  - Test PPTX → Markdown: verify slide separation, shapes/text, notes
  - Test PPTX → XLIFF: verify translation units per slide
  - Test PPTX → both: verify both outputs created
  - Test edge cases: PPTX with notes, shapes, grouped objects
  - Use sample files from conftest fixtures

  **Must NOT do**:
  - Modify source PPTX files
  - Leave temp files behind
  - Test DOCX or PDF in this file

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: E2E testing with presentation-specific features (slides, notes, shapes)
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8)
  - **Blocks**: Task 11
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_integration.py` - E2E test structure (use as primary pattern)
  - `tests/test_pptx_extractor.py` - PPTX test patterns (use for format-specific content verification)

  **WHY Each Reference Matters**:
  - test_integration.py: Shows how to test full pipeline with tmp_path fixture (PRIMARY PATTERN for E2E)
  - test_pptx_extractor.py: Shows how to test slide content, notes extraction

  **Acceptance Criteria**:

  - [ ] File created: tests/test_pptx_e2e.py
  - [ ] Tests for PPTX → Markdown output (verify slides, shapes, notes)
  - [ ] Tests for PPTX → XLIFF output (verify trans units per slide)
  - [ ] Tests for PPTX → both (verify both files created)
  - [ ] All tests pass with `pytest tests/test_pptx_e2e.py -v`

  **QA Scenarios**:

  ```
  Scenario: PPTX → MD separates slides with headings
    Tool: Bash
    Preconditions: PPTX with 3 slides
    Steps:
      1. Run opp with --target-format=md on PPTX
      2. Read generated .md file
      3. Verify "## Slide 1", "## Slide 2", "## Slide 3" headings
    Expected Result: Each slide gets a heading
    Evidence: .sisyphus/evidence/task-6-pptx-md-slides.txt
  ```

  **Evidence to Capture:**
  - [ ] MD output with slide headings

  **Commit**: YES (group 4)
  - Message: `test(e2e): add PPTX end-to-end tests`
  - Files: `tests/test_pptx_e2e.py`
  - Pre-commit: `pytest tests/test_pptx_e2e.py -v`

- [x] 7. **PDF End-to-End Tests (test_pdf_e2e.py)**

  **What to do**:
  - Create `tests/test_pdf_e2e.py`
  - Test PDF → Markdown: verify text extraction, table structure, image references
  - Test PDF → XLIFF: verify error message (PDF not supported for XLIFF)
  - Test edge cases: PDF with tables, multi-column layout, images
  - Use sample files from conftest fixtures

  **Must NOT do**:
  - Modify source PDF files
  - Leave temp files behind
  - Test DOCX or PPTX in this file

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: E2E testing with PDF-specific features (tables, multi-column, OCR potential)
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8)
  - **Blocks**: Task 11
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_integration.py` - E2E test structure (use as primary pattern)
  - `tests/test_pdf_extractor.py` - PDF test patterns (use for format-specific content verification)

  **WHY Each Reference Matters**:
  - test_integration.py: Shows how to test full pipeline with tmp_path fixture (PRIMARY PATTERN for E2E)
  - test_pdf_extractor.py: Shows how to test PDF-specific content (tables, multi-column)

  **Acceptance Criteria**:

  - [ ] File created: tests/test_pdf_e2e.py
  - [ ] Tests for PDF → Markdown output (verify text, tables, images)
  - [ ] Tests for PDF → XLIFF output (verify error: "not supported")
  - [ ] Tests for PDF with complex layouts
  - [ ] All tests pass with `pytest tests/test_pdf_e2e.py -v`

  **QA Scenarios**:

  ```
  Scenario: PDF → MD extracts text correctly
    Tool: Bash
    Preconditions: Native PDF with known text content
    Steps:
      1. Run opp with --target-format=md on PDF
      2. Read generated .md file
      3. Verify expected text appears
    Expected Result: Text extracted correctly
    Evidence: .sisyphus/evidence/task-7-pdf-md-text.txt

  Scenario: PDF → XLIFF returns error
    Tool: Bash
    Preconditions: Valid PDF file
    Steps:
      1. Run opp with --target-format=xlf on PDF
      2. Verify error message: "XLIFF output not supported for PDF format"
      3. Verify no .xlf file created
    Expected Result: Clear error, no crash
    Evidence: .sisyphus/evidence/task-7-pdf-xliff-error.txt
  ```

  **Evidence to Capture:**
  - [ ] PDF MD output
  - [ ] PDF XLIFF error message

  **Commit**: YES (group 4)
  - Message: `test(e2e): add PDF end-to-end tests`
  - Files: `tests/test_pdf_e2e.py`
  - Pre-commit: `pytest tests/test_pdf_e2e.py -v`

- [x] 8. **OPP→OL Integration Tests (test_opp_ol_integration.py)**

  **What to do**:
  - Create `tests/test_opp_ol_integration.py`
  - Create mock OL tool (shell script or Python stub) that:
    - Accepts XLIFF input file
    - Simulates translation by adding "_translated" to target content
    - Outputs modified XLIFF
  - Test full pipeline: OPP convert → OL translate → verify output
  - Test BDD scenario: `opp convert spec.docx --target-format=both --output-dir preprocess/`
  - Verify MD and XLIFF content match (paragraphs align)
  - Verify mock OL produces valid output that can be applied

  **Must NOT do**:
  - Require real OL tool installation
  - Make network calls
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration testing with external tool mock, complex workflow validation
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Task 11
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_integration.py` - Integration test structure
  - BDD scenario in OPP_DD_Vibe_Phase版.md - Expected workflow

  **WHY Each Reference Matters**:
  - test_integration.py: Shows how to test pipeline with multiple components
  - BDD scenario: Defines expected OPP→OL workflow

  **Acceptance Criteria**:

  - [ ] File created: tests/test_opp_ol_integration.py
  - [ ] Mock OL tool created and callable
  - [ ] Tests for OPP → XLIFF → OL translate pipeline
  - [ ] Tests for MD/XLIFF content alignment verification
  - [ ] Tests for BDD scenario workflow
  - [ ] All tests pass with `pytest tests/test_opp_ol_integration.py -v`

  **QA Scenarios**:

  ```
  Scenario: Mock OL tool processes XLIFF
    Tool: Bash
    Preconditions: Valid XLIFF file
    Steps:
      1. Create mock OL tool
      2. Call mock OL with XLIFF input
      3. Verify output XLIFF has modified targets
    Expected Result: Mock OL produces translated XLIFF
    Evidence: .sisyphus/evidence/task-8-mock-ol-output.txt

  Scenario: OPP → OL pipeline produces expected outputs
    Tool: Bash
    Preconditions: Valid DOCX file, mock OL installed
    Steps:
      1. Run `opp convert sample.docx --target-format=both --output-dir test_output/`
      2. Verify test_output/sample.md exists
      3. Verify test_output/sample.xlf exists
      4. Call mock OL on sample.xlf
      5. Verify translated XLIFF output exists
    Expected Result: Full pipeline works with mock OL
    Evidence: .sisyphus/evidence/task-8-full-pipeline.txt
  ```

  **Evidence to Capture:**
  - [ ] Mock OL output
  - [ ] Full pipeline execution

  **Commit**: YES (group 5)
  - Message: `test(integration): add OPP→OL integration tests`
  - Files: `tests/test_opp_ol_integration.py`, `tests/mock_ol.py`
  - Pre-commit: `pytest tests/test_opp_ol_integration.py -v`

- [x] 9. **GitHub Actions Workflow for PyPI Publishing**

  **What to do**:
  - Create `.github/workflows/publish.yml`
  - Configure for:
    - Trigger on version tags (v*)
    - Run tests: pytest with coverage
    - Build package: python -m build
    - Publish to TestPyPI first (for verification)
    - Publish to PyPI only on manual confirmation or after TestPyPI success
  - Use trusted publishing (OIDC) for security
  - Include job to verify version sync
  - Document required secrets/permissions in workflow comments

  **Must NOT do**:
  - Hardcode API tokens in workflow
  - Publish on every push (only on tags)
  - Skip tests before publishing
  - Use deprecated actions (use up-to-date versions)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard GitHub Actions workflow, straightforward YAML
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11)
  - **Blocks**: Task 10
  - **Blocked By**: None (independent)

  **References**:

  **Pattern References** (existing code to follow):
  - hatchling publishing docs - Build configuration

  **External References** (libraries and frameworks):
  - GitHub Actions: https://docs.github.com/en/actions
  - PyPI trusted publishing: https://docs.pypi.org/trusted-publishers/

  **WHY Each Reference Matters**:
  - hatchling docs: Shows correct build command and metadata
  - PyPI trusted publishing: Security best practice (no token in secrets)

  **Acceptance Criteria**:

  - [ ] File created: .github/workflows/publish.yml
  - [ ] Workflow triggers on version tags (v*)
  - [ ] Tests run before build
  - [ ] Package builds successfully
  - [ ] TestPyPI publishing step included
  - [ ] PyPI publishing step included (with manual trigger option)
  - [ ] Version verification job included

  **QA Scenarios**:

  ```
  Scenario: Workflow file is valid YAML
    Tool: Bash
    Preconditions: .github/workflows/publish.yml created
    Steps:
      1. Run `python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"`
      2. Verify no syntax errors
    Expected Result: Valid YAML, parses without error
    Evidence: .sisyphus/evidence/task-9-workflow-valid.txt

  Scenario: Workflow structure is correct
    Tool: Bash
    Preconditions: Workflow file exists
    Steps:
      1. Read workflow file
      2. Verify on: push: tags: - 'v*'
      3. Verify jobs include test, build, publish-to-testpypi
    Expected Result: Correct trigger and job structure
    Evidence: .sisyphus/evidence/task-9-workflow-structure.txt
  ```

  **Evidence to Capture:**
  - [ ] YAML validation output
  - [ ] Workflow structure verification

  **Commit**: YES (group 6)
  - Message: `ci(pypi): add GitHub Actions publishing workflow`
  - Files: `.github/workflows/publish.yml`
  - Pre-commit: N/A (workflow validation only)

- [x] 10. **TestPyPI Publishing Verification**

  **What to do**:
  - Test the publishing workflow by creating a TestPyPI release
  - Use a pre-release version (e.g., 0.1.1a0) for testing
  - Verify:
    - Package uploads successfully to TestPyPI
    - Package can be installed from TestPyPI in fresh venv
    - All dependencies resolve correctly
    - Package imports work (import opp)
  - Document the TestPyPI URL for manual verification
  - Create a github tag for the test version after verification

  **Must NOT do**:
  - Publish to real PyPI (only TestPyPI for verification)
  - Use the production version number (0.1.0 is already on PyPI)
  - Leave test artifacts behind

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Package publishing verification, straightforward steps
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 11)
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:

  **Pattern References** (existing code to follow):
  - `.github/workflows/publish.yml` - Created in Task 9

  **External References** (libraries and frameworks):
  - TestPyPI: https://test.pypi.org/
  - twine: Package publishing tool

  **WHY Each Reference Matters**:
  - publish.yml: Shows the workflow that will be triggered
  - TestPyPI: Where to verify package before production release

  **Acceptance Criteria**:

  - [ ] Test package published to TestPyPI (version 0.1.1a0)
  - [ ] Package installs from TestPyPI in fresh venv
  - [ ] `import opp` works in installed package
  - [ ] Dependencies resolve correctly
  - [ ] Documentation of TestPyPI URL provided

  **QA Scenarios**:

  ```
  Scenario: Package published to TestPyPI
    Tool: Bash
    Preconditions: GitHub Actions workflow exists
    Steps:
      1. Create git tag v0.1.1a0
      2. Push tag to GitHub
      3. Watch Actions workflow run
      4. Verify package appears on TestPyPI
    Expected Result: Package available at https://test.pypi.org/project/opp/
    Evidence: .sisyphus/evidence/task-10-testpypi-published.txt

  Scenario: Package installs from TestPyPI
    Tool: Bash
    Preconditions: Package on TestPyPI
    Steps:
      1. Create fresh venv
      2. Run pip install from TestPyPI URL
      3. Verify `python -c "import opp; print(opp.__version__)"` works
    Expected Result: Package installs and imports correctly
    Evidence: .sisyphus/evidence/task-10-install-test.txt
  ```

  **Evidence to Capture:**
  - [ ] TestPyPI URL confirmation
  - [ ] Installation verification

  **Commit**: NO (verification only, uses tag push)

- [x] 11. **Final Verification + Cleanup**

  **What to do**:
  - Run all Phase 4 tests: pytest tests/test_cli.py tests/test_docx_e2e.py tests/test_pptx_e2e.py tests/test_pdf_e2e.py tests/test_opp_ol_integration.py -v
  - Verify all imports work: from opp import cli, pipeline, markdown, xliff
  - Verify CLI help shows new flags
  - Verify version sync works
  - Verify GitHub Actions workflow is valid YAML
  - Generate final report showing Phase 4 completion
  - Clean up any temp files from testing

  **Must NOT do**:
  - Skip any test
  - Ignore test failures
  - Proceed without all tests passing

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Final verification requiring comprehensive check across all components
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (final check)
  - **Parallel Group**: Wave 3 (with Tasks 9, 10) - but sequential execution
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 5, 6, 7, 8, 10

  **References**:

  **Test References** (testing patterns to follow):
  - All Phase 4 test files

  **WHY Each Reference Matters**:
  - All test files: Must verify all pass together

  **Acceptance Criteria**:

  - [ ] All Phase 4 tests pass (100%)
  - [ ] All imports work correctly
  - [ ] CLI shows all new flags in help
  - [ ] Version sync verified
  - [ ] GitHub Actions workflow valid
  - [ ] No temp files left behind
  - [ ] Final report generated

  **QA Scenarios**:

  ```
  Scenario: Full test suite execution
    Tool: Bash
    Preconditions: All Phase 4 code implemented
    Steps:
      1. Run pytest tests/test_cli.py tests/test_docx_e2e.py tests/test_pptx_e2e.py tests/test_pdf_e2e.py tests/test_opp_ol_integration.py -v
      2. Verify all tests pass
    Expected Result: 100% test pass rate
    Evidence: .sisyphus/evidence/task-11-final-tests.txt

  Scenario: CLI help verification
    Tool: Bash
    Preconditions: Package installed
    Steps:
      1. Run opp --help
      2. Verify --target-format, --source-lang, --target-lang, --output-dir appear
    Expected Result: Help shows all new flags
    Evidence: .sisyphus/evidence/task-11-cli-help.txt

  Scenario: Import verification
    Tool: Bash
    Preconditions: All Phase 4 modules exist
    Steps:
      1. Run python -c "from opp import cli, pipeline, markdown; from opp.xliff.generator import XLIFFFileGenerator; print('All imports OK')"
      2. Verify no ImportError
    Expected Result: All imports successful
    Evidence: .sisyphus/evidence/task-11-imports.txt
  ```

  **Evidence to Capture:**
  - [ ] Full test suite output
  - [ ] CLI help output
  - [ ] Import verification

  **Commit**: NO (final verification only)

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [11/11] | Must NOT Have [3/3] | Tasks [86/86] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + linter. Review all changed files for: empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Build [PASS] | Tests [240 pass/0 fail] | Files [4 clean/0 issues] | VERDICT: PASS`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [5/5 pass] | Integration [1/1] | Edge Cases [2/2 tested] | VERDICT: PASS`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [11/11 compliant] | Contamination [CLEAN/0 issues] | Unaccounted [CLEAN/0 files] | VERDICT: APPROVED`

---

## Commit Strategy

- **1**: `feat(cli): add --target-format, --source-lang, --target-lang flags` - src/opp/cli.py, tests/test_cli.py
- **2**: `feat(pipeline): add MD/XLIFF generation methods` - src/opp/pipeline.py
- **3**: `fix(version): use hatchling dynamic versioning from __init__.py` - pyproject.toml
- **4**: `test(e2e): add DOCX/PPTX/PDF end-to-end tests` - tests/test_docx_e2e.py, tests/test_pptx_e2e.py, tests/test_pdf_e2e.py
- **5**: `test(integration): add OPP→OL integration tests` - tests/test_opp_ol_integration.py
- **6**: `ci(pypi): add GitHub Actions publishing workflow` - .github/workflows/publish.yml

---

## Success Criteria

### Verification Commands
```bash
opp --help  # Shows --target-format, --source-lang, --target-lang
opp --target-format=md sample.docx  # Creates sample.md
opp --target-format=xlf --source-lang=en --target-lang=zh sample.docx  # Creates sample.xlf
pytest tests/test_cli.py tests/test_docx_e2e.py tests/test_pptx_e2e.py tests/test_pdf_e2e.py tests/test_opp_ol_integration.py -v  # All pass
python -c "from opp import __version__; print(__version__)"  # Shows version
```

### Final Checklist
- [ ] --target-format, --source-lang, --target-lang, --output-dir flags work
- [ ] DOCX/PPTX/PDF → MD output works correctly
- [ ] DOCX/PPTX → XLIFF output works correctly
- [ ] PDF → XLIFF returns error (not supported)
- [ ] OPP→OL integration tests pass (mock OL)
- [ ] Version sync resolved (single source of truth in __init__.py)
- [ ] GitHub Actions workflow exists for PyPI publishing
- [ ] All pytest tests pass
- [ ] No regression in existing Phase 0-3 functionality