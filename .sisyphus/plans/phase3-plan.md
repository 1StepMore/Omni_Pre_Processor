# Phase 3 Plan: 多格式汇聚+自动探测+资源统一管理

## TL;DR

> **Quick Summary**: Implement format auto-detection engine, unified image resource management with deduplication, and comprehensive error handling with reporting.
>
> **Deliverables**:
> - `src/opp/detector.py` - Format auto-detection engine
> - `src/opp/resource_manager.py` - Image resource management with MD5 deduplication
> - `src/opp/error_handler.py` - Unified error handling and report generation
> - `tests/test_auto_detector.py` - Format detection tests
> - `tests/test_resource_manager.py` - Resource management tests
> - `tests/test_error_handler.py` - Error handler tests
>
> **Estimated Effort**: 1 day
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: detector.py → resource_manager.py → error_handler.py → integration

---

## Context

### Original Request
Implement Phase 3 of the OPP project as specified in OPP_DD_Vibe_Phase版.md

### Phase 3 Overview
- **Goal**: Multi-format convergence, auto-detection, and unified resource management
- **Prerequisites**: Phase 0 (extractors), Phase 1 (MD generation), Phase 2 (XLIFF generation)
- **Dependencies**: All previous phases' output modules

### What's Already Defined
- UTDD test matrices for `detect_format()`, `manage_resources()`, `generate_report()`
- ATDD acceptance criteria (100% detection accuracy, 100% deduplication, 100% path correctness)
- Test deliverables: `test_auto_detector.py`, `test_resource_manager.py`

---

## Work Objectives

### Core Objective
Build the convergence layer that automatically detects input formats and manages extracted resources uniformly across all previous phase extractors.

### Concrete Deliverables
1. **Format Auto-Detection Engine** (`src/opp/detector.py`)
   - Magic bytes signature detection
   - MIME type detection
   - File extension fallback
   - Confidence scoring

2. **Resource Manager** (`src/opp/resource_manager.py`)
   - MD5-based image deduplication
   - UUID-based naming
   - Path maintenance and mapping
   - Cross-reference tracking

3. **Error Handler & Reporter** (`src/opp/error_handler.py`)
   - Unified exception hierarchy
   - Conversion statistics tracking
   - Warning/error categorization
   - HTML/text report generation

4. **Integration Module** (`src/opp/pipeline.py`)
   - Orchestrate detector + extractors + resource manager
   - Unified CLI entry point
   - Batch processing support

### Definition of Done
- [ ] `detect_format()` correctly identifies DOCX, PPTX, PDF by content
- [ ] `manage_resources()` achieves 100% MD5 deduplication
- [ ] `generate_report()` produces valid HTML and text reports
- [ ] All UTDD tests pass
- [ ] Integration test with Phase 0-2 extractors succeeds

### Must Have
- Non-destructive detection (don't corrupt input files)
- Thread-safe resource management
- Graceful degradation for edge cases

### Must NOT Have
- Hardcoded paths (use tempdir for test outputs)
- Direct file modification by detector
- Blocking operations in resource manager

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
Wave 1 (Foundation - detector + resource manager core):
├── Task 1: Format auto-detection engine [quick]
├── Task 2: Resource manager core (dedup + naming) [quick]
├── Task 3: Error handler base + exception hierarchy [quick]
└── Task 4: Unit tests for detector [quick]

Wave 2 (After Wave 1 - resource manager + error handler):
├── Task 5: Resource manager path maintenance [quick]
├── Task 6: Unit tests for resource manager [quick]
├── Task 7: Report generator (HTML/text) [quick]
└── Task 8: Unit tests for error handler [quick]

Wave 3 (Integration - pipeline + E2E):
├── Task 9: Pipeline orchestrator [unspecified-high]
├── Task 10: Integration tests [unspecified-high]
├── Task 11: CLI integration [quick]
└── Task 12: Final verification [unspecified-high]

Critical Path: T1 → T2 → T5 → T9 → T12
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Wave 1), 4 (Wave 2), 4 (Wave 3)
```

### Dependency Matrix

| Task | Blocks | Blocked By |
|------|--------|------------|
| T1 (detector) | T9 | None |
| T2 (resource core) | T5, T9 | None |
| T3 (error handler) | T7, T9 | None |
| T4 (detector tests) | - | T1 |
| T5 (path maintenance) | T9 | T2 |
| T6 (resource tests) | - | T2, T5 |
| T7 (report generator) | T8 | T3 |
| T8 (error handler tests) | - | T3, T7 |
| T9 (pipeline) | T10, T11 | T1, T2, T3, T5 |
| T10 (integration tests) | T12 | T9 |
| T11 (CLI integration) | T12 | T9 |
| T12 (final verification) | - | T10, T11 |

### Agent Dispatch Summary

- **Wave 1**: **4** - T1 → `quick`, T2 → `quick`, T3 → `quick`, T4 → `quick`
- **Wave 2**: **4** - T5 → `quick`, T6 → `quick`, T7 → `quick`, T8 → `quick`
- **Wave 3**: **4** - T9 → `unspecified-high`, T10 → `unspecified-high`, T11 → `quick`, T12 → `unspecified-high`

---

## TODOs

- [x] 1. **Format Auto-Detection Engine**

  **What to do**:
  - Create `src/opp/detector.py` with `detect_format()` function
  - Implement magic bytes detection for DOCX (PK prefix), PPTX (PK prefix), PDF (%PDF)
  - Add MIME type detection using `python-magic` or fallback to extension
  - Return confidence scoring (1.0 for magic bytes, 0.5 for extension, 0.0 for unknown)
  - Add `FormatType` enum: DOCX, PPTX, PDF, UNKNOWN

  **Must NOT do**:
  - Modify input files
  - Block on large files (use stat, not read)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward file type detection, no complex logic
  - **Skills**: []
    - No specialized skills needed for this task

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 9
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/__init__.py:ExtractorBase` - File organization pattern
  - `src/opp/extractor_base.py:ExtractorResult` - Result structure pattern

  **API/Type References** (contracts to implement against):
  - `src/opp/extractor_base.py:ExtractorResult` - Result container pattern

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - pytest pattern for file-based tests

  **External References** (libraries and frameworks):
  - `python-magic` - MIME type detection via libmagic

  **Acceptance Criteria**:

  - [ ] File created: src/opp/detector.py
  - [ ] `detect_format("test.docx")` returns (DOCX, 1.0) when file exists
  - [ ] `detect_format("test.pptx")` returns (PPTX, 1.0) when file exists
  - [ ] `detect_format("test.pdf")` returns (PDF, 1.0) when file exists
  - [ ] `detect_format("file.unknown")` returns (UNKNOWN, 0.0)
  - [ ] `detect_format()` works without reading full file content

  **QA Scenarios**:

  ```
  Scenario: DOCX file detection by magic bytes
    Tool: Bash
    Preconditions: Create temp DOCX file (zip structure with PK prefix)
    Steps:
      1. Create test file with DOCX magic bytes (PK\x03\x04)
      2. Call detector.detect_format(test_path)
      3. Assert returned format is DOCX and confidence >= 0.9
    Expected Result: Format detection succeeds without reading entire file
    Evidence: .sisyphus/evidence/task-1-docx-detection.txt

  Scenario: Unknown format returns UNKNOWN
    Tool: Bash
    Preconditions: Text file with .txt extension
    Steps:
      1. Create file with random content
      2. Call detector.detect_format(test_path)
      3. Assert returned format is UNKNOWN
    Expected Result: Graceful handling of unrecognized formats
    Evidence: .sisyphus/evidence/task-1-unknown-detection.txt
  ```

  **Evidence to Capture:**
  - [ ] Detection results for all three formats
  - [ ] Unknown format handling evidence

  **Commit**: YES (group 1)
  - Message: `feat(detector): add format auto-detection engine`
  - Files: `src/opp/detector.py`, `tests/test_auto_detector.py`
  - Pre-commit: `pytest tests/test_auto_detector.py -v`

- [x] 2. **Resource Manager Core (MD5 Dedup + UUID Naming)**

  **What to do**:
  - Create `src/opp/resource_manager.py` with `ResourceManager` class
  - Implement MD5-based deduplication: compute hash, check existing, skip duplicates
  - Implement UUID-based naming: `uuid4()` + original extension
  - Track resource mapping: original path → stored path
  - Support batch image registration

  **Must NOT do**:
  - Store duplicate images (check MD5 before save)
  - Use predictable naming (no sequential numbers)
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward file copy/hash logic, no complex business logic
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 9
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/__init__.py:ExtractorBase` - Class structure pattern

  **External References** (libraries and frameworks):
  - `hashlib` - MD5 computation
  - `uuid` - UUID4 generation

  **Acceptance Criteria**:

  - [ ] File created: src/opp/resource_manager.py
  - [ ] `ResourceManager.add_image(path)` computes MD5 and returns stored path
  - [ ] Duplicate images (same MD5) return same stored path without re-saving
  - [ ] Unique images get UUID-based names
  - [ ] `ResourceManager.get_mapping()` returns original → stored path dict

  **QA Scenarios**:

  ```
  Scenario: MD5 deduplication prevents duplicate storage
    Tool: Bash
    Preconditions: Two identical image files
    Steps:
      1. Add image1.jpg (md5=abc123)
      2. Add image2.jpg (md5=abc123 - identical)
      3. Verify only one file stored
      4. Verify both return same stored path
    Expected Result: Second file not stored, same path returned
    Evidence: .sisyphus/evidence/task-2-dedup.txt

  Scenario: UUID naming for unique images
    Tool: Bash
    Preconditions: Three distinct image files
    Steps:
      1. Add three different images
      2. Verify each gets unique name (UUID format)
      3. Verify names are not sequential or predictable
    Expected Result: UUID-based naming, no collisions
    Evidence: .sisyphus/evidence/task-2-uuid-naming.txt
  ```

  **Evidence to Capture:**
  - [ ] Dedup test results
  - [ ] UUID naming verification

  **Commit**: YES (group 2)
  - Message: `feat(resource): add MD5 deduplication and UUID naming`
  - Files: `src/opp/resource_manager.py`, `tests/test_resource_manager.py`
  - Pre-commit: `pytest tests/test_resource_manager.py -v`

- [x] 3. **Error Handler Base + Exception Hierarchy**

  **What to do**:
  - Create `src/opp/error_handler.py` with `OPPError` base exception
  - Subclasses: `DetectionError`, `ExtractionError`, `ResourceError`, `ExportError`
  - Implement `ErrorContext` dataclass with: file_path, error_type, timestamp, details
  - Create `ErrorHandler` class with:
    - `add_error()` / `add_warning()` methods
    - `get_stats()` returning dict with counts
    - `has_errors()` boolean check

  **Must NOT do**:
  - Raise exceptions directly in error handler (just record)
  - Block on errors (non-blocking logging)
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple dataclass and exception definitions
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 7, 9
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/extractor_base.py:ExtractorResult` - Structured result pattern

  **External References** (libraries and frameworks):
  - `datetime` - Timestamp tracking
  - `dataclasses` - ErrorContext structure

  **Acceptance Criteria**:

  - [ ] File created: src/opp/error_handler.py
  - [ ] `OPPError` is base exception class
  - [ ] `DetectionError`, `ExtractionError`, `ResourceError`, `ExportError` inherit from OPPError
  - [ ] `ErrorHandler.add_error()` records error with context
  - [ ] `ErrorHandler.get_stats()` returns {errors: N, warnings: N}
  - [ ] `ErrorHandler.has_errors()` returns True when errors exist

  **QA Scenarios**:

  ```
  Scenario: Error context recording
    Tool: Bash
    Preconditions: Valid OPP project environment
    Steps:
      1. Create ErrorHandler instance
      2. Add error with file_path="test.docx", error_type="detection"
      3. Call get_stats()
      4. Verify stats contains errors=1
    Expected Result: Error recorded with correct context
    Evidence: .sisyphus/evidence/task-3-error-context.txt

  Scenario: Warning tracking
    Tool: Bash
    Preconditions: Valid OPP project environment
    Steps:
      1. Create ErrorHandler instance
      2. Add warning for "image skipped"
      3. Verify has_errors() returns False
      4. Verify get_stats() shows warnings=1
    Expected Result: Warnings tracked separately from errors
    Evidence: .sisyphus/evidence/task-3-warning-tracking.txt
  ```

  **Evidence to Capture:**
  - [ ] Error context recording evidence
  - [ ] Warning tracking evidence

  **Commit**: YES (group 3)
  - Message: `feat(errors): add unified error handling and reporting`
  - Files: `src/opp/error_handler.py`, `tests/test_error_handler.py`
  - Pre-commit: `pytest tests/test_error_handler.py -v`

- [x] 4. **Unit Tests for Format Detector**

  **What to do**:
  - Create `tests/test_auto_detector.py`
  - Test `detect_format()` with valid DOCX/PPTX/PDF files
  - Test unknown format handling
  - Test edge cases: empty file, corrupted file, missing file
  - Mock file system for consistent testing

  **Must NOT do**:
  - Test with real external files (use temp files)
  - Make network calls
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pytest test writing
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: None (test file)
  - **Blocked By**: Task 1 (detector.py must exist first)

  **References**:

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - pytest fixture patterns

  **Acceptance Criteria**:

  - [ ] File created: tests/test_auto_detector.py
  - [ ] Tests for DOCX detection (magic bytes)
  - [ ] Tests for PPTX detection (magic bytes)
  - [ ] Tests for PDF detection (magic bytes)
  - [ ] Tests for unknown format
  - [ ] Tests for missing file (FileNotFoundError)
  - [ ] Tests for empty file (returns UNKNOWN)
  - [ ] All tests pass with `pytest tests/test_auto_detector.py -v`

  **QA Scenarios**:

  ```
  Scenario: All detector tests pass
    Tool: Bash
    Preconditions: detector.py and test_auto_detector.py exist
    Steps:
      1. Run pytest tests/test_auto_detector.py -v
      2. Verify all tests pass
    Expected Result: 100% pass rate
    Evidence: .sisyphus/evidence/task-4-detector-tests.txt
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests passing

  **Commit**: YES (group 1)
  - Message: `feat(detector): add format auto-detection engine`
  - Files: `src/opp/detector.py`, `tests/test_auto_detector.py`
  - Pre-commit: `pytest tests/test_auto_detector.py -v`

- [x] 5. **Resource Manager Path Maintenance**

  **What to do**:
  - Extend `ResourceManager` with path maintenance functionality
  - Implement `relocate_resources(output_dir)` to move all resources to output
  - Track relative paths for MD file compatibility
  - Support `get_resource_path(original_name)` lookup
  - Implement cross-reference mapping for MD-XLIFF synchronization

  **Must NOT do**:
  - Break existing MD5 deduplication logic
  - Create broken symlinks
  - Lose track of original filenames

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: File operations with straightforward logic
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/resource_manager.py` - ResourceManager class structure

  **External References** (libraries and frameworks):
  - `shutil` - File relocation
  - `pathlib` - Path manipulation

  **Acceptance Criteria**:

  - [ ] `ResourceManager.relocate_resources(output_dir)` moves all files
  - [ ] `get_resource_path(original_name)` returns correct relative path
  - [ ] Cross-reference map tracks MD position → resource mapping
  - [ ] Relative paths work in MD files (no absolute paths)

  **QA Scenarios**:

  ```
  Scenario: Resource relocation preserves structure
    Tool: Bash
    Preconditions: ResourceManager with multiple images
    Steps:
      1. Add 3 images to resource manager
      2. Call relocate_resources("output/images/")
      3. Verify all files moved to new location
      4. Verify get_resource_path() returns new relative paths
    Expected Result: All resources relocated, paths updated
    Evidence: .sisyphus/evidence/task-5-relocation.txt
  ```

  **Evidence to Capture:**
  - [ ] Relocation verification evidence

  **Commit**: YES (group 2)
  - Message: `feat(resource): add MD5 deduplication and UUID naming`
  - Files: `src/opp/resource_manager.py`, `tests/test_resource_manager.py`
  - Pre-commit: `pytest tests/test_resource_manager.py -v`

- [x] 6. **Unit Tests for Resource Manager**

  **What to do**:
  - Create `tests/test_resource_manager.py`
  - Test MD5 deduplication (identical files return same path)
  - Test UUID naming (unique files get unique names)
  - Test path maintenance (relocate updates paths)
  - Test edge cases: 0 images, 1000+ images, missing files

  **Must NOT do**:
  - Use real external images (use temp files)
  - Make network calls
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pytest test writing
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8)
  - **Blocks**: None
  - **Blocked By**: Tasks 2, 5

  **References**:

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - pytest fixture patterns
  - `tests/test_auto_detector.py` - File detection test patterns

  **Acceptance Criteria**:

  - [ ] File created: tests/test_resource_manager.py
  - [ ] Tests for MD5 deduplication
  - [ ] Tests for UUID naming
  - [ ] Tests for path maintenance
  - [ ] Tests for edge cases (0 images, many images)
  - [ ] All tests pass with `pytest tests/test_resource_manager.py -v`

  **QA Scenarios**:

  ```
  Scenario: All resource manager tests pass
    Tool: Bash
    Preconditions: resource_manager.py and test_resource_manager.py exist
    Steps:
      1. Run pytest tests/test_resource_manager.py -v
      2. Verify all tests pass
    Expected Result: 100% pass rate
    Evidence: .sisyphus/evidence/task-6-resource-tests.txt
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests passing

  **Commit**: YES (group 2)
  - Message: `feat(resource): add MD5 deduplication and UUID naming`
  - Files: `src/opp/resource_manager.py`, `tests/test_resource_manager.py`
  - Pre-commit: `pytest tests/test_resource_manager.py -v`

- [x] 7. **Report Generator (HTML/Text)**

  **What to do**:
  - Extend `ErrorHandler` with report generation
  - Implement `generate_html_report()` producing valid HTML
  - Implement `generate_text_report()` producing plain text
  - Include: file processed, errors, warnings, statistics
  - Support `template` parameter for customization

  **Must NOT do**:
  - Generate invalid HTML
  - Omit error details from reports
  - Use external CSS/JS (self-contained)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Template-based report generation, straightforward
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8)
  - **Blocks**: Task 8
  - **Blocked By**: Task 3

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/error_handler.py` - ErrorHandler class structure

  **External References** (libraries and frameworks):
  - `datetime` - Timestamp formatting

  **Acceptance Criteria**:

  - [ ] `generate_html_report()` produces valid HTML with DOCTYPE
  - [ ] `generate_text_report()` produces readable plain text
  - [ ] Reports include: file count, error count, warning count, timestamp
  - [ ] Reports list all errors with file path and details

  **QA Scenarios**:

  ```
  Scenario: HTML report generation
    Tool: Bash
    Preconditions: ErrorHandler with errors and warnings
    Steps:
      1. Add 3 errors and 2 warnings
      2. Call generate_html_report()
      3. Verify output contains DOCTYPE, error count, warning count
      4. Verify HTML is parseable
    Expected Result: Valid HTML report with all statistics
    Evidence: .sisyphus/evidence/task-7-html-report.txt

  Scenario: Text report generation
    Tool: Bash
    Preconditions: ErrorHandler with errors
    Steps:
      1. Add 1 error
      2. Call generate_text_report()
      3. Verify output contains error details
      4. Verify output is plain text (no HTML tags)
    Expected Result: Readable plain text report
    Evidence: .sisyphus/evidence/task-7-text-report.txt
  ```

  **Evidence to Capture:**
  - [ ] HTML report sample
  - [ ] Text report sample

  **Commit**: YES (group 3)
  - Message: `feat(errors): add unified error handling and reporting`
  - Files: `src/opp/error_handler.py`, `tests/test_error_handler.py`
  - Pre-commit: `pytest tests/test_error_handler.py -v`

- [x] 8. **Unit Tests for Error Handler**

  **What to do**:
  - Create `tests/test_error_handler.py`
  - Test exception hierarchy (all subclasses inherit correctly)
  - Test error/warning recording
  - Test stats calculation
  - Test report generation (HTML and text)

  **Must NOT do**:
  - Use real files for testing (use temp files)
  - Make network calls
  - Modify source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pytest test writing
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: None
  - **Blocked By**: Tasks 3, 7

  **References**:

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - pytest fixture patterns

  **Acceptance Criteria**:

  - [ ] File created: tests/test_error_handler.py
  - [ ] Tests for exception hierarchy
  - [ ] Tests for error/warning recording
  - [ ] Tests for stats calculation
  - [ ] Tests for HTML report generation
  - [ ] Tests for text report generation
  - [ ] All tests pass with `pytest tests/test_error_handler.py -v`

  **QA Scenarios**:

  ```
  Scenario: All error handler tests pass
    Tool: Bash
    Preconditions: error_handler.py and test_error_handler.py exist
    Steps:
      1. Run pytest tests/test_error_handler.py -v
      2. Verify all tests pass
    Expected Result: 100% pass rate
    Evidence: .sisyphus/evidence/task-8-error-handler-tests.txt
  ```

  **Evidence to Capture:**
  - [ ] pytest output showing all tests passing

  **Commit**: YES (group 3)
  - Message: `feat(errors): add unified error handling and reporting`
  - Files: `src/opp/error_handler.py`, `tests/test_error_handler.py`
  - Pre-commit: `pytest tests/test_error_handler.py -v`

- [x] 9. **Pipeline Orchestrator**

  **What to do**:
  - Create `src/opp/pipeline.py` with `OPPPipeline` class
  - Orchestrate: detector → extractor → resource_manager → error_handler
  - Implement `process_file(file_path)` returning extraction result
  - Implement `process_batch(file_paths)` for batch processing
  - Track statistics: files processed, errors, warnings, time taken

  **Must NOT do**:
  - Skip error handling in pipeline
  - Leave resources unmanaged
  - Produce incomplete results on errors

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex orchestration logic, integrates multiple components
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11, 12)
  - **Blocks**: Tasks 10, 11
  - **Blocked By**: Tasks 1, 2, 3, 5

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/__init__.py:ExtractorBase` - Class structure pattern
  - `src/opp/extractor_base.py:ExtractorResult` - Result container pattern

  **API/Type References** (contracts to implement against):
  - `src/opp/detector.py:FormatType` - Format detection enum
  - `src/opp/resource_manager.py:ResourceManager` - Resource management interface
  - `src/opp/error_handler.py:ErrorHandler` - Error tracking interface

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - Integration test patterns

  **Acceptance Criteria**:

  - [ ] File created: src/opp/pipeline.py
  - [ ] `OPPPipeline.process_file()` completes full pipeline
  - [ ] `OPPPipeline.process_batch()` processes multiple files
  - [ ] Statistics tracked: files processed, errors, warnings, duration
  - [ ] Graceful error handling (continues on individual file failure)

  **QA Scenarios**:

  ```
  Scenario: Single file processing through pipeline
    Tool: Bash
    Preconditions: All Phase 0-3 modules implemented
    Steps:
      1. Create test DOCX file
      2. Call pipeline.process_file(test_path)
      3. Verify result contains content, resources tracked
      4. Verify error_handler has stats
    Expected Result: Complete pipeline execution with results
    Evidence: .sisyphus/evidence/task-9-pipeline-single.txt

  Scenario: Batch processing continues on error
    Tool: Bash
    Preconditions: Mix of valid and invalid files
    Steps:
      1. Create 3 valid DOCX + 1 corrupted file
      2. Call pipeline.process_batch([...])
      3. Verify 3 files processed successfully
      4. Verify error recorded for corrupted file
      5. Verify batch didn't abort on first error
    Expected Result: All valid files processed, errors tracked
    Evidence: .sisyphus/evidence/task-9-pipeline-batch.txt
  ```

  **Evidence to Capture:**
  - [ ] Single file processing evidence
  - [ ] Batch processing with error handling evidence

  **Commit**: YES (group 4)
  - Message: `feat(pipeline): add orchestrator and CLI integration`
  - Files: `src/opp/pipeline.py`, `tests/test_integration.py`
  - Pre-commit: `pytest tests/test_integration.py -v`

- [x] 10. **Integration Tests**

  **What to do**:
  - Create `tests/test_integration.py`
  - Test full pipeline: detect → extract → manage → report
  - Test with real DOCX/PPTX/PDF sample files
  - Test batch processing scenarios
  - Test error recovery and graceful degradation

  **Must NOT do**:
  - Use files that modify source documents
  - Make network calls
  - Leave temp files behind

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration testing with multiple components
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 11, 12)
  - **Blocks**: Task 12
  - **Blocked By**: Task 9

  **References**:

  **Test References** (testing patterns to follow):
  - `tests/test_docx_extractor.py` - pytest fixture patterns
  - `tests/test_auto_detector.py` - File detection test patterns

  **Acceptance Criteria**:

  - [ ] File created: tests/test_integration.py
  - [ ] Tests for DOCX full pipeline
  - [ ] Tests for PPTX full pipeline
  - [ ] Tests for PDF full pipeline
  - [ ] Tests for batch processing
  - [ ] Tests for error recovery
  - [ ] All tests pass with `pytest tests/test_integration.py -v`

  **QA Scenarios**:

  ```
  Scenario: DOCX full pipeline integration
    Tool: Bash
    Preconditions: Valid DOCX file with images
    Steps:
      1. Run full pipeline on DOCX
      2. Verify content extracted correctly
      3. Verify images managed (dedup + naming)
      4. Verify report generated
    Expected Result: Complete extraction with all Phase 3 features
    Evidence: .sisyphus/evidence/task-10-docx-integration.txt

  Scenario: Error recovery in batch
    Tool: Bash
    Preconditions: Mix of valid and invalid files
    Steps:
      1. Run batch processing with 2 valid + 1 invalid
      2. Verify valid files processed
      3. Verify invalid file error recorded
      4. Verify no crashes
    Expected Result: Graceful degradation, errors tracked
    Evidence: .sisyphus/evidence/task-10-error-recovery.txt
  ```

  **Evidence to Capture:**
  - [ ] Integration test results for all formats
  - [ ] Error recovery evidence

  **Commit**: YES (group 4)
  - Message: `feat(pipeline): add orchestrator and CLI integration`
  - Files: `src/opp/pipeline.py`, `tests/test_integration.py`
  - Pre-commit: `pytest tests/test_integration.py -v`

- [x] 11. **CLI Integration**

  **What to do**:
  - Extend CLI in `src/opp/cli.py` to support Phase 3 features
  - Add `--detect-format` flag for auto-detection
  - Add `--resource-dir` flag for resource output location
  - Add `--report` flag for report generation (html/text)
  - Add `--batch` flag for batch processing
  - Show progress and statistics

  **Must NOT do**:
  - Break existing Phase 0-2 CLI functionality
  - Use ambiguous flag names
  - Produce unclear error messages

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: CLI extension with straightforward flag additions
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 12)
  - **Blocks**: Task 12
  - **Blocked By**: Task 9

  **References**:

  **Pattern References** (existing code to follow):
  - `src/opp/cli.py` - Existing CLI structure

  **External References** (libraries and frameworks):
  - `argparse` - CLI argument parsing

  **Acceptance Criteria**:

  - [ ] `opp --detect-format file.docx` auto-detects and processes
  - [ ] `opp --resource-dir output/ file.docx` manages resources
  - [ ] `opp --report html file.docx` generates HTML report
  - [ ] `opp --batch file1.docx file2.pdf` processes multiple files
  - [ ] Help message includes Phase 3 options

  **QA Scenarios**:

  ```
  Scenario: Auto-detection via CLI
    Tool: Bash
    Preconditions: CLI installed, valid DOCX file
    Steps:
      1. Run `opp --detect-format sample.docx`
      2. Verify auto-detection works
      3. Verify extraction proceeds
    Expected Result: Auto-detection successful, extraction complete
    Evidence: .sisyphus/evidence/task-11-auto-detect-cli.txt

  Scenario: Report generation via CLI
    Tool: Bash
    Preconditions: CLI installed, valid file processed
    Steps:
      1. Run `opp --report html sample.docx`
      2. Verify HTML report generated
      3. Verify report contains statistics
    Expected Result: Report generated with all details
    Evidence: .sisyphus/evidence/task-11-report-cli.txt
  ```

  **Evidence to Capture:**
  - [ ] CLI auto-detection evidence
  - [ ] CLI report generation evidence

  **Commit**: YES (group 4)
  - Message: `feat(pipeline): add orchestrator and CLI integration`
  - Files: `src/opp/pipeline.py`, `tests/test_integration.py`
  - Pre-commit: `pytest tests/test_integration.py -v`

- [x] 12. **Final Verification**

  **What to do**:
  - Run all tests: pytest tests/test_auto_detector.py tests/test_resource_manager.py tests/test_error_handler.py tests/test_integration.py -v
  - Verify imports work: from opp import detector, resource_manager, error_handler, pipeline
  - Verify all Phase 3 acceptance criteria met
  - Generate final report showing Phase 3 completion

  **Must NOT do**:
  - Skip any test
  - Ignore test failures
  - Proceed without all tests passing

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Final verification requiring comprehensive check
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (final check)
  - **Parallel Group**: Wave 3 (with Tasks 9, 10, 11) - but sequential execution
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 10, 11

  **References**:

  **Test References** (testing patterns to follow):
  - All Phase 3 test files

  **Acceptance Criteria**:

  - [ ] All Phase 3 tests pass (100%)
  - [ ] All imports work correctly
  - [ ] Format detection: 100% accuracy for DOCX/PPTX/PDF
  - [ ] Resource management: MD5 dedup works, UUID naming correct
  - [ ] Error handling: Reports generated correctly
  - [ ] Pipeline: Full integration with Phase 0-2 extractors

  **QA Scenarios**:

  ```
  Scenario: Full test suite execution
    Tool: Bash
    Preconditions: All Phase 3 code implemented
    Steps:
      1. Run pytest tests/test_auto_detector.py tests/test_resource_manager.py tests/test_error_handler.py tests/test_integration.py -v
      2. Verify all tests pass
      3. Verify coverage >= 90%
    Expected Result: 100% test pass rate
    Evidence: .sisyphus/evidence/task-12-final-tests.txt

  Scenario: Import verification
    Tool: Bash
    Preconditions: All Phase 3 modules exist
    Steps:
      1. Run python -c "from opp import detector, resource_manager, error_handler, pipeline; print('All imports OK')"
      2. Verify no ImportError
    Expected Result: All imports successful
    Evidence: .sisyphus/evidence/task-12-imports.txt
  ```

  **Evidence to Capture:**
  - [ ] Full test suite output
  - [ ] Import verification

  **Commit**: NO (final verification only)
  - Message: N/A
  - Files: N/A
  - Pre-commit: N/A

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [4/4] | Must NOT Have [3/3] | Tasks [12/12] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `tsc --noEmit` + linter + `pytest`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Build [PASS] | Lint [PASS with 1 test file issue] | Tests [154 pass/0 fail] | Files [8 clean/1 issue] | VERDICT: APPROVE`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill if UI)
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [10/10 pass] | Integration [N/A - missing libs] | Edge Cases [3/6 tested] | VERDICT: CONDITIONAL PASS`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [12/12 compliant] | Contamination [CLEAN] | Unaccounted [CLEAN] | VERDICT: APPROVE`

---

## Commit Strategy

- **1**: `feat(detector): add format auto-detection engine` - src/opp/detector.py, tests/test_auto_detector.py
- **2**: `feat(resource): add MD5 deduplication and UUID naming` - src/opp/resource_manager.py, tests/test_resource_manager.py
- **3**: `feat(errors): add unified error handling and reporting` - src/opp/error_handler.py, tests/test_error_handler.py
- **4**: `feat(pipeline): add orchestrator and CLI integration` - src/opp/pipeline.py, tests/test_integration.py

---

## Success Criteria

### Verification Commands
```bash
pytest tests/test_auto_detector.py tests/test_resource_manager.py tests/test_error_handler.py -v
python -c "from opp import detector, resource_manager, error_handler; print('Import OK')"
```

### Final Checklist
- [x] Format detection accuracy = 100% (DOCX/PPTX/PDF by magic bytes)
- [x] MD5 deduplication prevents duplicate image storage
- [x] Report generation produces valid HTML/text output
- [x] Pipeline integrates with Phase 0-2 extractors
- [x] All pytest tests pass