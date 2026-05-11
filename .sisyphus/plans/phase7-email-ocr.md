# OPP Phase 7: Email & Image OCR Extension

## TL;DR

> **Quick Summary**: Implement EML/MSG email extraction and Image OCR text extraction to complete OPP's format coverage.
>
> **Deliverables**:
> - `src/opp/extractors/email.py` - Email extractor (EML/MSG)
> - `src/opp/extractors/image_ocr.py` - Image OCR extractor
> - `tests/test_email_extractor.py` - Email extractor tests
> - `tests/test_image_ocr_extractor.py` - Image OCR extractor tests
>
> **Estimated Effort**: 1.5 days
> **Parallel Execution**: YES - 2.5 waves (Wave 1 → Wave 1.5 → Wave 2)
> **Critical Path**: Task 1 → Task 1.5 → Task 3 → Task 6 → Task 9

---

## Context

### Original Request
User wants Phase 7 plan for OPP (Omni Pre-Processor) based on OPP增补完整版.md

### Interview Summary
**Phase 7 Coverage** (from OPP增补完整版.md, lines 821-944):
- Email formats: EML (RFC 822) and MSG (Outlook)
- Image OCR: Text extraction from scanned documents/screenshots
- Tools: extract_msg, email stdlib, pytesseract/rapidocr-onnxruntime, Pillow
- Tests: test_email_extractor.py, test_image_ocr_extractor.py
- ATDD criteria: 100% metadata extraction, ≥95% OCR accuracy

### Technical Approach
- **Email**: Use extract_msg for MSG, email stdlib for EML
- **OCR**: Pluggable architecture (Tesseract default, RapidOCR as alternative)
- **Recursion**: Attachment handling with depth limit (≤3)
- **Integration**: HTML email → Phase 6 channel; Plain text → paragraph channel

---

## Work Objectives

### Core Objective
Implement email (EML/MSG) extraction and Image OCR text extraction as Phase 7 of OPP development plan.

### Concrete Deliverables
- [x] `src/opp/extractors/email.py` - Email extractor with EML/MSG support
- [x] `src/opp/extractors/image_ocr.py` - Image OCR extractor with pluggable engines
- [x] `tests/test_email_extractor.py` - Email extraction tests
- [x] `tests/test_image_ocr_extractor.py` - OCR extraction tests
- [x] CLI integration for `--ocr-engine` flag
- [x] AttachmentHandler abstraction for recursive processing

### Definition of Done
- [ ] `pytest tests/test_email_extractor.py` passes (all email extraction tests)
- [ ] `pytest tests/test_image_ocr_extractor.py` passes (all OCR tests)
- [ ] `opp convert email.msg --target-format both` produces valid MD+XLIFF
- [ ] `opp convert image.png --ocr-engine tesseract` produces MD with extracted text
- [ ] Email attachment recursion depth ≤ 3, logs processing chain

### Must Have
- MSG and EML format support with 100% metadata extraction
- OCR text extraction with ≥95% accuracy on 300dpi samples
- Graceful degradation when OCR engine not installed
- Attachment recursive processing (depth limited)

### Must NOT Have
- No IMAP/POP3 server connectivity (file-based only)
- No browser automation for JS-rendered email content
- No unlimited recursion (max depth 3 for attachments)
- No OCR cloud API dependencies in core package

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD cycle)
- **Framework**: pytest
- **TDD Cycle**: RED (failing tests) → GREEN (implementation) → REFACTOR

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Email extraction**: Use Bash (Python) - Import extractor, call extract functions, verify output
- **OCR extraction**: Use Bash (Python) - Import extractor, call OCR function, verify text output
- **CLI integration**: Use Bash - Run opp commands, verify exit code and output files

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - can run immediately):
├── Task 1: Project structure + dependencies
└── Task 1.5: FormatType + OPPPipeline registration (NEW - after T1)

Wave 1.5 (Email implementation):
├── Task 2: Email base extractor + tests (RED phase)
├── Task 3: MSG extractor implementation (GREEN phase)
├── Task 4: EML extractor implementation (GREEN phase)
└── Task 5: Email tests completion (REFACTOR phase)

Wave 2 (OCR - depends on Wave 1.5 for patterns):
├── Task 6: Image OCR base extractor + tests (RED phase)
├── Task 7: Tesseract OCR implementation (GREEN phase)
├── Task 8: RapidOCR implementation (GREEN phase)
├── Task 9: OCR graceful degradation (GREEN phase)
├── Task 10: CLI integration for OCR (REFACTOR phase)
└── Task 11: Email-OCR integration + attachment handler

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit
├── Task F2: Code quality review
├── Task F3: Real manual QA
└── Task F4: Scope fidelity check
```

### Dependency Matrix

- **T1.5**: 1 - 3, 4, 5, 11 (NEW: FormatType + Pipeline registration)
- **T1**: - - 1.5, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
- **T2**: 1, 1.5 - 5, 2
- **T3**: 2 - 5, 11, 2
- **T4**: 2 - 5, 11, 2
- **T5**: 3, 4 - 2
- **T6**: 1, 1.5 - 7, 8, 9, 10, 6
- **T7**: 6 - 9, 10, 6
- **T8**: 6 - 9, 10, 6
- **T9**: 7, 8 - 10, 6
- **T10**: 9 - 11, 6
- **T11**: 5, 10 - F1, F2, F3, F4

---

## TODOs

- [x] 1. Project structure + dependencies
- [x] 1.5. FormatType enum update + OPPPipeline registration (NEW)

- [ ] 2. Email base extractor + RED tests

  **What to do**:
  - Write test file `tests/test_email_extractor.py` with:
    - `test_extract_msg_metadata()` - Extract From/To/Date/Subject from MSG
    - `test_extract_eml_metadata()` - Extract From/To/Date/Subject from EML
    - `test_extract_msg_body()` - Extract plain text body
    - `test_extract_eml_html_body()` - Extract HTML body
    - `test_extract_msg_attachments()` - Extract attachment list
    - `test_extract_eml_attachments()` - Extract attachment list
    - `test_corrupted_msg()` - Handle corrupted MSG gracefully
    - `test_encoding_error_eml()` - Handle encoding errors
  - All tests should FAIL initially (RED phase)

  **Must NOT do**:
  - No actual implementation yet - tests drive implementation
  - No full EML/MSG parsing - keep tests focused

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Test writing following existing patterns
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: Tasks 3, 4, 5
  - **Blocked By**: Task 1

  **References**:
  - `tests/test_docx_extractor.py` - Test structure pattern
  - `extract_msg` library docs - MSG parsing API
  - Python `email` stdlib docs - EML parsing API

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_email_extractor.py -v` runs
  - [ ] All tests FAIL (expected for RED phase)

  **QA Scenarios**:

  Scenario: Tests fail as expected (RED phase)
    Tool: Bash
    Preconditions: Task 1 complete, tests written
    Steps:
      1. `pytest tests/test_email_extractor.py -v`
      2. Assert: All tests show FAILED status
    Expected Result: Tests fail with "NotImplementedError" or similar
    Failure Indicators: Tests pass unexpectedly
    Evidence: .sisyphus/evidence/task-2-red-phase.txt

  **Commit**: YES
  - Message: `test(phase7): add email extractor RED phase tests`
  - Files: `tests/test_email_extractor.py`

---

- [ ] 3. MSG extractor implementation

  **What to do**:
  - Implement `EmailExtractor` class that inherits from `ExtractorBase`
  - Implement `extract(self, input_path: Path) -> ExtractionResult`:
    - Detect if file is MSG (by extension or OLE signature)
    - Route to `_extract_msg()` for MSG files
  - Implement private `_extract_msg(path)`:
    - Use `extract_msg` library to parse MSG file
    - Extract: sender, to, cc, date, subject, body (plain + HTML)
    - Return structured result with metadata and body
  - Handle: encrypted MSG (raise error), corrupted MSG (catch exception)
  - Implement `_extract_msg_attachments()` - list attachment filenames

  **API Clarification**: The public `extract()` method dispatches to `_extract_msg()` or `_extract_eml()` internally. Do NOT create separate public `extract_msg()` or `extract_eml()` methods - the base class contract uses `extract()`.

  **Must NOT do**:
  - No IMAP connectivity
  - No MSG creation/writing
  - No processing attachments (only listing)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: MSG parsing with COM interop complexity
  - **Skills**: []
    - No specialized skills but requires deep implementation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 4, 5)
  - **Blocks**: Task 5
  - **Blocked By**: Task 2

  **References**:
  - `extract_msg` library - `read_msg()` function returns Message object
  - `src/opp/extractors/base.py` - Base extractor pattern
  - Existing extractor implementations for style reference

  **Acceptance Criteria**:
  - [ ] Test `test_extract_msg_metadata` passes
  - [ ] Test `test_extract_msg_body` passes
  - [ ] Test `test_extract_msg_attachments` passes
  - [ ] Test `test_corrupted_msg` passes (graceful error handling)

  **QA Scenarios**:

  Scenario: MSG metadata extraction
    Tool: Bash
    Preconditions: Task 1.5 complete, implementation ready, fixture exists
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); r = e.extract('tests/fixtures/email/sample.msg'); print(r.metadata)"`
      3. Assert: metadata contains sender, to, date, subject
    Expected Result: All metadata fields present
    Failure Indicators: Missing fields, KeyError
    Evidence: .sisyphus/evidence/task-3-msg-metadata.json

  Scenario: MSG body extraction
    Tool: Bash
    Preconditions: Sample MSG with body content
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); r = e.extract('tests/fixtures/email/sample.msg'); print(r.body[:100])"`
    Expected Result: Body text extracted
    Failure Indicators: Empty body, encoding errors
    Evidence: .sisyphus/evidence/task-3-msg-body.txt

  Scenario: Corrupted MSG handling
    Tool: Bash
    Preconditions: Corrupted MSG file
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); e.extract('tests/fixtures/email/corrupted.msg')"`
    Expected Result: Raises informative error, not crash
    Failure Indicators: Unhandled exception, crash
    Evidence: .sisyphus/evidence/task-3-msg-error.json

  **Commit**: YES
  - Message: `feat(phase7): implement MSG extractor`
  - Files: `src/opp/extractors/email.py`

---

- [ ] 4. EML extractor implementation

  **What to do**:
  - Implement private `_extract_eml(path)` method in `EmailExtractor`:
    - Use Python `email` stdlib to parse EML file
    - Extract: From, To, Cc, Date, Subject via `email.message_from_bytes()`
    - Handle multipart: extract text/plain and text/html parts
    - Use charset detection for non-UTF8 emails
  - Handle: encoding errors (fallback to chardet), missing headers
  - The `extract()` base method already dispatches to this - do not create a separate public method

  **API Clarification**: `_extract_eml()` is a private method called by `extract()`. The EmailExtractor already knows how to route EML files to this method based on the FormatType detection.

  **Must NOT do**:
  - No SMTP/IMAP connectivity
  - No email sending capability
  - No processing nested EML attachments (treat as binary)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: EML parsing with encoding complexity
  - **Skills**: []
    - No specialized skills but requires encoding handling

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 5)
  - **Blocks**: Task 5
  - **Blocked By**: Task 2

  **References**:
  - Python `email` stdlib documentation
  - `email.policy.EmailPolicy` for header parsing
  - `email.message_from_bytes()` API

  **Acceptance Criteria**:
  - [ ] Test `test_extract_eml_metadata` passes
  - [ ] Test `test_extract_eml_html_body` passes
  - [ ] Test `test_extract_eml_attachments` passes
  - [ ] Test `test_encoding_error_eml` passes (chardet fallback)

  **QA Scenarios**:

  Scenario: EML metadata extraction
    Tool: Bash
    Preconditions: Task 1.5 complete
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); r = e.extract('tests/fixtures/email/sample.eml'); print(r.metadata)"`
    Expected Result: All headers present
    Failure Indicators: Missing headers, decoding errors
    Evidence: .sisyphus/evidence/task-4-eml-metadata.json

  Scenario: EML HTML body extraction
    Tool: Bash
    Preconditions: HTML email sample
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); r = e.extract('tests/fixtures/email/html_email.eml'); print(r.body)"`
    Expected Result: HTML content extracted
    Failure Indicators: Empty body
    Evidence: .sisyphus/evidence/task-4-eml-html.txt

  Scenario: Encoding error handling
    Tool: Bash
    Preconditions: EML with wrong encoding declared
    Steps:
      1. `python -c "from opp.extractors.email import EmailExtractor; e = EmailExtractor(); r = e.extract('tests/fixtures/email/bad_encoding.eml')"`
    Expected Result: Graceful handling with chardet fallback
    Failure Indicators: Crash, UnicodeDecodeError
    Evidence: .sisyphus/evidence/task-4-eml-encoding.json

  **Commit**: YES
  - Message: `feat(phase7): implement EML extractor`
  - Files: `src/opp/extractors/email.py`

---

- [ ] 5. Email tests completion + attachment handler

  **What to do**:
  - Complete all email tests (TDD GREEN phase)
  - Add `AttachmentHandler` class for recursive attachment processing:
    - `process_attachment(attachment_path)` - Call OPP pipeline recursively
    - `get_recursion_depth()` - Track current depth
    - Max depth limit = 3
  - Integrate email extractor with OPPPipeline

  **Must NOT do**:
  - No infinite recursion
  - No processing of dangerous attachment types

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Recursion handling and integration
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 11
  - **Blocked By**: Tasks 3, 4

  **References**:
  - `src/opp/pipeline.py` - OPPPipeline integration pattern
  - `src/opp/resource_manager.py` - Resource handling pattern

  **Acceptance Criteria**:
  - [ ] All email tests pass
  - [ ] `pytest tests/test_email_extractor.py` → 100% pass
  - [ ] Attachment recursion depth limited to 3
  - [ ] Integration with OPPPipeline works

  **QA Scenarios**:

  Scenario: All email tests pass
    Tool: Bash
    Preconditions: Tasks 2, 3, 4 complete
    Steps:
      1. `pytest tests/test_email_extractor.py -v`
      2. Assert: All tests PASSED
    Expected Result: 100% pass rate
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-email-tests.txt

  Scenario: Attachment recursion limit
    Tool: Bash
    Preconditions: MSG with nested attachments
    Steps:
      1. Write test for recursion depth tracking
      2. Assert: depth ≤ 3 after processing
    Expected Result: Recursion stops at depth 3
    Failure Indicators: Infinite recursion, depth > 3
    Evidence: .sisyphus/evidence/task-5-recursion.json

  **Commit**: YES
  - Message: `test(phase7): complete email tests and add attachment handler`
  - Files: `tests/test_email_extractor.py`, `src/opp/extractors/email.py`

---

- [ ] 6. Image OCR base extractor + RED tests

  **What to do**:
  - Write test file `tests/test_image_ocr_extractor.py`:
    - `test_extract_text_from_image()` - Basic PNG text extraction
    - `test_extract_chinese_text()` - Chinese OCR (requires chi_sim Tesseract)
    - `test_extract_low_resolution_warning()` - 72dpi warning
    - `test_no_text_in_image()` - Empty result for风景图
    - `test_corrupted_image()` - Handle损坏图片
    - `test_ocr_engine_not_installed()` - Graceful degradation
    - `test_tesseract_vs_rapidocr()` - Multi-engine comparison
  - All tests should FAIL initially (RED phase)
  - Use fixture images from `tests/fixtures/ocr/` created in Task 1

  **Must NOT do**:
  - No actual OCR implementation yet
  - No cloud OCR API calls

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Test writing following patterns
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9, 10)
  - **Blocks**: Tasks 7, 8, 9, 10
  - **Blocked By**: Task 1

  **References**:
  - `tests/test_email_extractor.py` - Test structure pattern
  - `pytesseract` documentation - OCR API

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_image_ocr_extractor.py -v` runs
  - [ ] All tests FAIL (expected for RED phase)

  **QA Scenarios**:

  Scenario: Tests fail as expected (RED phase)
    Tool: Bash
    Preconditions: Task 1 complete, tests written
    Steps:
      1. `pytest tests/test_image_ocr_extractor.py -v`
      2. Assert: All tests show FAILED status
    Expected Result: Tests fail with NotImplementedError
    Failure Indicators: Tests pass unexpectedly
    Evidence: .sisyphus/evidence/task-6-red-phase.txt

  **Commit**: YES
  - Message: `test(phase7): add image OCR extractor RED phase tests`
  - Files: `tests/test_image_ocr_extractor.py`

---

- [ ] 7. Tesseract OCR implementation

  **What to do**:
  - Implement `ImageOCRExtractor.extract_text(image_path, engine='tesseract')`:
    - Use `pytesseract` to extract text from image
    - Preprocess image: convert to RGB, apply threshold if needed
    - Extract text with language config (eng, chi_sim, etc.)
    - Return: extracted text, confidence score, language
  - Support: PNG, JPG, TIFF, BMP formats

  **Must NOT do**:
  - No video frame extraction
  - No handwriting recognition specifically
  - No cloud API fallback (handled separately)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: OCR implementation with preprocessing
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 8, 9, 10)
  - **Blocks**: Task 9, 10
  - **Blocked By**: Task 6

  **References**:
  - `pytesseract` documentation
  - Pillow image preprocessing docs
  - Tesseract language codes

  **Acceptance Criteria**:
  - [ ] Test `test_extract_text_from_image` passes
  - [ ] Test `test_extract_chinese_text` passes (if Tesseract has chi_sim)
  - [ ] Test `test_low_resolution_warning` passes (72dpi detection)

  **QA Scenarios**:

  Scenario: Basic text extraction
    Tool: Bash
    Preconditions: Sample image with text at `tests/fixtures/ocr/sample.png`
    Steps:
      1. `python -c "from opp.extractors.image_ocr import ImageOCRExtractor; e = ImageOCRExtractor(); r = e.extract_text('tests/fixtures/ocr/sample.png'); print(r['text'][:100])"`
    Expected Result: Text extracted from image
    Failure Indicators: Empty text, error
    Evidence: .sisyphus/evidence/task-7-tesseract-basic.txt

  Scenario: Chinese text extraction
    Tool: Bash
    Preconditions: Chinese text image sample at `tests/fixtures/ocr/chinese.png`, Tesseract chi_sim installed
    Steps:
      1. `python -c "from opp.extractors.image_ocr import ImageOCRExtractor; e = ImageOCRExtractor(); r = e.extract_text('tests/fixtures/ocr/chinese.png', lang='chi_sim'); print(r['text'])"`
    Expected Result: Chinese text extracted
    Failure Indicators: Empty result, garbled text
    Evidence: .sisyphus/evidence/task-7-tesseract-chinese.txt

  **Commit**: YES
  - Message: `feat(phase7): implement Tesseract OCR`
  - Files: `src/opp/extractors/image_ocr.py`

---

- [ ] 8. RapidOCR implementation

  **What to do**:
  - Implement `ImageOCRExtractor.extract_text(image_path, engine='rapidocr')`:
    - Use `rapidocr_onnxruntime` for OCR
    - Auto-detect language (English/Chinese mixed)
    - Return same interface as Tesseract: text, confidence, language
  - Pluggable architecture: both engines return identical output structure

  **Must NOT do**:
  - No model downloading in code (assume models pre-installed)
  - No GPU-specific optimization

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Alternative OCR engine implementation
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 9, 10)
  - **Blocks**: Task 9, 10
  - **Blocked By**: Task 6

  **References**:
  - `rapidocr_onnxruntime` documentation
  - Existing ImageOCRExtractor class structure

  **Acceptance Criteria**:
  - [ ] Test `test_tesseract_vs_rapidocr` passes (same output structure)
  - [ ] Both engines return: {text, confidence, language}
  - [ ] Engine switching works via config

  **QA Scenarios**:

  Scenario: RapidOCR text extraction
    Tool: Bash
    Preconditions: Task 7 complete, RapidOCR installed
    Steps:
      1. `python -c "from opp.extractors.image_ocr import ImageOCRExtractor; e = ImageOCRExtractor(); r = e.extract_text('test.png', engine='rapidocr'); print(r['text'][:100])"`
    Expected Result: Text extracted via RapidOCR
    Failure Indicators: Engine not found error
    Evidence: .sisyphus/evidence/task-8-rapidocr.txt

  Scenario: Engine consistency
    Tool: Bash
    Preconditions: Both engines available
    Steps:
      1. Compare output structure from both engines
      2. Assert: Same keys in returned dict
    Expected Result: Identical output structure
    Failure Indicators: Different return formats
    Evidence: .sisyphus/evidence/task-8-engine-consistency.json

  **Commit**: YES
  - Message: `feat(phase7): implement RapidOCR engine support`
  - Files: `src/opp/extractors/image_ocr.py`

---

- [ ] 9. OCR graceful degradation

  **What to do**:
  - Implement fallback behavior when OCR engine not installed:
    - Check if Tesseract is available via `which tesseract`
    - Check if RapidOCR imports succeed
    - If none available: return {text: "", error: "OCR_NOT_INSTALLED", install_guide: "..."}
  - Add OCR engine detection to extractor init
  - Provide helpful error messages with installation instructions

  **Must NOT do**:
  - No silent failures
  - No crash on missing OCR
  - No automatic cloud API fallback

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Error handling and user guidance
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 10)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 7, 8

  **References**:
  - `src/opp/error_handler.py` - Error handling pattern

  **Acceptance Criteria**:
  - [ ] Test `test_ocr_engine_not_installed` passes
  - [ ] Graceful error with install guide when no OCR available
  - [ ] No crash when Tesseract binary missing

  **QA Scenarios**:

  Scenario: Missing OCR engine handling
    Tool: Bash
    Preconditions: No Tesseract installed
    Steps:
      1. `python -c "from opp.extractors.image_ocr import ImageOCRExtractor; e = ImageOCRExtractor(); r = e.extract_text('test.png')"`
    Expected Result: Error response with install guide, no crash
    Failure Indicators: Unhandled exception
    Evidence: .sisyphus/evidence/task-9-missing-ocr.json

  Scenario: Low resolution warning
    Tool: Bash
    Preconditions: Image with <72dpi
    Steps:
      1. `python -c "from opp.extractors.image_ocr import ImageOCRExtractor; e = ImageOCRExtractor(); r = e.extract_text('low_res.png'); print(r.get('warning'))"`
    Expected Result: Warning about low resolution
    Failure Indicators: No warning emitted
    Evidence: .sisyphus/evidence/task-9-low-res-warning.txt

  **Commit**: YES
  - Message: `feat(phase7): add OCR graceful degradation`
  - Files: `src/opp/extractors/image_ocr.py`

---

- [ ] 10. CLI integration for OCR

  **What to do**:
  - Add `--ocr-engine` flag to CLI:
    - `opp convert image.png --ocr-engine tesseract`
    - `opp convert image.png --ocr-engine rapidocr`
    - Default: tesseract if available, else rapidocr
  - Add `--ocr-lang` flag for language selection:
    - `opp convert scan.png --ocr-lang eng`
    - `opp convert scan.png --ocr-lang chi_sim`
  - Update CLI help text with OCR options

  **Must NOT do**:
  - No default cloud OCR API
  - No automatic language detection (unless requested)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: CLI flag addition
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: Task 11
  - **Blocked By**: Task 9

  **References**:
  - `src/opp/cli.py` - CLI implementation

  **Acceptance Criteria**:
  - [ ] `opp convert image.png --ocr-engine tesseract` works
  - [ ] `opp convert image.png --ocr-engine rapidocr` works
  - [ ] `opp --help` shows OCR options

  **QA Scenarios**:

  Scenario: CLI OCR flag tesseract
    Tool: Bash
    Preconditions: Tesseract installed
    Steps:
      1. `opp convert test.png --ocr-engine tesseract -o output.md`
      2. Assert: Exit code 0, output.md created
    Expected Result: Success
    Failure Indicators: Invalid flag error
    Evidence: .sisyphus/evidence/task-10-cli-tesseract.txt

  Scenario: CLI OCR flag rapidocr
    Tool: Bash
    Preconditions: RapidOCR installed
    Steps:
      1. `opp convert test.png --ocr-engine rapidocr -o output.md`
      2. Assert: Exit code 0, output.md created
    Expected Result: Success
    Failure Indicators: Invalid flag error
    Evidence: .sisyphus/evidence/task-10-cli-rapidocr.txt

  **Commit**: YES
  - Message: `feat(phase7): add OCR CLI options`
  - Files: `src/opp/cli.py`

---

- [ ] 11. Email-OCR integration + attachment handler

  **What to do**:
  - Complete TDD REFACTOR phase:
    - Abstract `AttachmentHandler` for recursive processing
    - Integrate email extractor with OPPPipeline
    - Add OCR to image attachments from email
  - Ensure all Phase 7 tests pass:
    - `pytest tests/test_email_extractor.py`
    - `pytest tests/test_image_ocr_extractor.py`

  **Must NOT do**:
  - No breaking changes to existing OPPPipeline
  - No infinite recursion in attachment handling

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration and refactoring
  - **Skills**: []
    - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks F1, F2, F3, F4
  - **Blocked By**: Tasks 5, 10

  **References**:
  - `src/opp/pipeline.py` - OPPPipeline pattern
  - `src/opp/resource_manager.py` - ResourceManager pattern

  **Acceptance Criteria**:
  - [ ] All Phase 7 tests pass
  - [ ] Email attachments processed recursively
  - [ ] Image attachments in email go through OCR
  - [ ] OPPPipeline handles email format

  **QA Scenarios**:

  Scenario: Email with image attachment
    Tool: Bash
    Preconditions: Email with embedded image
    Steps:
      1. `opp convert email_with_image.msg --target-format both`
      2. Assert: Image attachment OCR processed
    Expected Result: Image text in output MD
    Failure Indicators: Image not processed
    Evidence: .sisyphus/evidence/task-11-email-image.txt

  Scenario: Full pipeline integration
    Tool: Bash
    Preconditions: Sample MSG with various attachments
    Steps:
      1. `pytest tests/test_email_extractor.py tests/test_image_ocr_extractor.py -v`
    Expected Result: 100% pass
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-11-full-tests.txt

  **Commit**: YES
  - Message: `feat(phase7): complete email-OCR integration`
  - Files: `src/opp/extractors/email.py`, `src/opp/pipeline.py`

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + linter. Review for: `as any`/`@ts-ignore` (not applicable in Python but check for bare except), empty catches, console.log (not applicable), unused imports.
  Output: `Tests [N/N pass] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task. Test with real MSG/EML files and images.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify diff. Check "Must NOT do" compliance.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **1**: `feat(phase7): add email and OCR extractor scaffolding` - pyproject.toml, email.py, image_ocr.py, fixtures
- **1.5**: `feat(phase7): add FormatType entries and OPPPipeline registration` - detector.py, pipeline.py, cli.py
- **2**: `test(phase7): add email extractor RED phase tests` - test_email_extractor.py
- **3**: `feat(phase7): implement MSG extractor` - email.py
- **4**: `feat(phase7): implement EML extractor` - email.py
- **5**: `test(phase7): complete email tests and add attachment handler` - test_email_extractor.py, email.py
- **6**: `test(phase7): add image OCR extractor RED phase tests` - test_image_ocr_extractor.py
- **7**: `feat(phase7): implement Tesseract OCR` - image_ocr.py
- **8**: `feat(phase7): implement RapidOCR engine support` - image_ocr.py
- **9**: `feat(phase7): add OCR graceful degradation` - image_ocr.py
- **10**: `feat(phase7): add OCR CLI options` - cli.py
- **11**: `feat(phase7): complete email-OCR integration` - email.py, pipeline.py

---

## Success Criteria

### Verification Commands
```bash
pytest tests/test_email_extractor.py -v  # All pass
pytest tests/test_image_ocr_extractor.py -v  # All pass
opp convert sample.msg --target-format both  # Generates MD + XLIFF
opp convert scan.png --ocr-engine tesseract  # OCR succeeds
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] CLI OCR flags work
- [ ] Attachment recursion depth limited
- [ ] Graceful degradation when OCR not installed