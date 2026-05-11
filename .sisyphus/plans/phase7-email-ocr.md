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

- [x] 2. Email base extractor + RED tests

- [x] 3. MSG extractor implementation

- [x] 4. EML extractor implementation

- [x] 5. Email tests completion + attachment handler

- [x] 6. Image OCR base extractor + RED tests

- [x] 7. Tesseract OCR implementation

- [x] 8. RapidOCR implementation

- [x] 9. OCR graceful degradation

- [x] 10. CLI integration for OCR

- [x] 11. Email-OCR integration + attachment handler

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle` ✅ APPROVE
  - Must Have [4/4] | Must NOT Have [4/4] | Tasks [11/11]

- [x] F2. **Code Quality Review** — `unspecified-high` ✅ CONDITIONAL PASS
  - Tests [12/12 pass] | Files [6 clean/2 LSP-expected] | 1 unused import noted

- [x] F3. **Real Manual QA** — `unspecified-high` ✅ APPROVE
  - Scenarios [15/15 PASS] | Integration [3/3 PASS]

- [x] F4. **Scope Fidelity Check** — `deep` ✅ PASS
  - Tasks [11/11 compliant] | Contamination [CLEAN/4 expected-LSP-issues]

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