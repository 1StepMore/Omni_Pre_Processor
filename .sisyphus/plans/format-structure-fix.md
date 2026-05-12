# Format Structure Preservation Fix Plan

## TL;DR

> **Quick Summary**: Fix structure preservation for EPUB, PPTX, PDF, and IPYNB extractors so that ParagraphData has correct `level` (1-6 for headings) and `style` (Heading1-6) when extracted.
>
> **Deliverables**:
> - EPUB: Headings extracted with correct level/style instead of `## text` in text field
> - PPTX: TITLE shapes mapped to level=1
> - PDF: TOC extraction via fitz.get_toc()
> - IPYNB: Markdown cells set level=1 instead of level=0
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 independent waves
> **Critical Path**: EPUB → PPTX → PDF → IPYNB (each independent)

---

## Context

### Problem Description
Multiple format extractors are not correctly populating `ParagraphData.level` and `ParagraphData.style` fields, causing structure (headings, chapters, TOC) to be lost when converting to MD/XLIFF.

### Coding Standards (DD Vibe.txt)
- **UTDD**: Write unit tests before writing code
- **ATDD**: Define acceptance criteria before coding
- **TDD**: Tests must pass before completion
- **BDD**: Use Given-When-Then for precise requirements

### Metis Review Findings
1. **EPUB data flow unclear** - `## text` conversion happens somewhere, need to confirm ParagraphData is source of truth
2. **PDF library check needed** - fitz (PyMuPDF) may already be in use
3. **Style name convention needed** - "Heading 1" vs "Heading1" vs "H1"
4. **Edge cases identified** - empty headings, duplicate text, headings in tables

---

## Work Objectives

### Core Objective
Fix extractors so MarkdownGenerator can correctly identify headings via `p.level >= 1` criteria.

### Concrete Deliverables
| Format | File | Fix |
|--------|------|-----|
| EPUB | `src/opp/extractors/epub.py` | Set `level=1-6` and `style="Heading N"` for h1-h6 tags |
| PPTX | `src/opp/extractors/pptx.py` | Set `level=1` for TITLE shape type |
| PDF | `src/opp/extractors/pdf.py` | Extract TOC via `doc.get_toc()` into ParagraphData |
| IPYNB | `src/opp/extractors/ipynb.py` | Set `level=1` for markdown cells (not 0) |

### Definition of Done
- [ ] `bun test` passes for all modified extractors
- [ ] Existing tests not broken
- [ ] MD output shows correct heading hierarchy for each format

### Must Have
- **UTDD**: Each implementation task writes tests FIRST (STEP 0), then implementation (STEP 1), then test gate (STEP 2)
- **ATDD**: All acceptance criteria defined with assertion syntax before coding
- **TDD**: Each task's STEP 2 gate must pass before task completion
- **BDD**: All QA scenarios use Given-When-Then format
- All changes are backward compatible
- No new dependencies added without explicit approval

### Must NOT Have
- Do NOT modify MarkdownGenerator behavior (only fix extractors)
- Do NOT change style name conventions from existing patterns
- Do NOT add heuristic TOC extraction for PDF (only bookmarks via fitz.get_toc())

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 4 tasks per wave. Fewer than 3 per wave = under-splitting.

```
Wave 1 (Investigation - 4 tasks in parallel, NO CODE CHANGES):
├── Task 1: Investigate EPUB data flow [quick]
├── Task 2: Investigate PDF library and TOC API [quick]
├── Task 3: Investigate PPTX TITLE shape mapping [quick]
└── Task 4: Investigate IPYNB cell level semantics [quick]

Wave 2 (Implementation - 4 tasks in parallel, DEPENDS ON WAVE 1):
├── Task 5: Fix EPUB extractor [deep] (blocked by 1)
├── Task 6: Fix PDF extractor TOC extraction [deep] (blocked by 2)
├── Task 7: Fix PPTX extractor TITLE mapping [deep] (blocked by 3)
└── Task 8: Fix IPYNB extractor markdown level [quick] (blocked by 4)

Wave FINAL (Verification - 4 tasks in parallel):
├── Task F1: Plan Compliance Audit [oracle]
├── Task F2: Code Quality Review [unspecified-high]
├── Task F3: Real Manual QA [unspecified-high]
└── Task F4: Scope Fidelity Check [deep]

Critical Path: T1 → T5 → Final
Parallel Speedup: ~60% faster than sequential (2 waves instead of 8 sequential)
Max Concurrent: 4 (Wave 1 and Wave 2 each have 4 independent tasks)
```

### Dependency Matrix

| Task | Can Start | Blocks |
|------|-----------|--------|
| 1 (EPUB investigate) | Immediately | 5 (EPUB fix) |
| 2 (PDF investigate) | Immediately | 6 (PDF fix) |
| 3 (PPTX investigate) | Immediately | 7 (PPTX fix) |
| 4 (IPYNB investigate) | Immediately | 8 (IPYNB fix) |
| 5 (EPUB fix) | After 1 complete | Final |
| 6 (PDF fix) | After 2 complete | Final |
| 7 (PPTX fix) | After 3 complete | Final |
| 8 (IPYNB fix) | After 4 complete | Final |
| F1-F4 | After 5,6,7,8 complete | User approval |

### Agent Dispatch Summary

- **Wave 1**: **4 quick** agents - T1, T2, T3, T4 run in parallel
- **Wave 2**: **3 deep + 1 quick** - T5 (deep), T6 (deep), T7 (deep), T8 (quick) run in parallel
- **Wave FINAL**: **1 oracle + 3 unspecified-high/deep** - F1 (oracle), F2 (unspecified-high), F3 (unspecified-high), F4 (deep)

---

## Verification Strategy

### DD Vibe Compliance
- **UTDD**: Tests written FIRST (STEP 0 in each implementation task)
- **ATDD**: Acceptance criteria defined with assertion syntax before coding
- **TDD**: Each task has STEP 2 gate - tests must pass before completion
- **BDD**: All QA scenarios use Given-When-Then format

### Test Decision
- **Infrastructure exists**: YES (pytest, 479+ tests)
- **Automated tests**: UTDD - write failing test first, then implementation
- **Framework**: pytest
- **QA Policy**: Each implementation task has 3 QA scenarios (BDD)

### QA Scenarios (per format - BDD Given-When-Then)
Each implementation task (T5-T8) has:
1. Happy path: Given-When-Then with valid heading extraction
2. Edge case: Given-When-Then with empty heading or special characters
3. Negative: Given-When-Then ensuring non-heading content unchanged

### Final Verification Wave (TDD Compliant)
Each F1-F4 task runs AFTER all T5-T8 STEP 2 gates pass:
- F1: Plan Compliance Audit - verify all Must Have implemented, Must NOT NOT violated
- F2: Code Quality Review - run `pytest tests/ -v`, ensure ALL pass
- F3: Real Manual QA - execute ALL Given-When-Then scenarios, capture evidence
- F4: Scope Fidelity Check - verify 1:1 spec-to-implementation

---

## DD Vibe Compliance

This plan follows DD Vibe coding standards:

- **UTDD**: Unit tests written BEFORE implementation (see STEP 0 in each implementation task)
- **ATDD**: Acceptance criteria defined BEFORE coding with assertion syntax
- **TDD**: Tests must pass before task completion (STEP 2 gate)
- **BDD**: All QA scenarios use Given-When-Then format

---

## TODO Execution Workflow

Each implementation task follows this structure:

```
STEP 0: Write Test FIRST (UTDD)
  → Write failing test based on acceptance criteria
  → Verify test FAILS before writing any implementation code

STEP 1: Implement (ATDD/TDD)
  → Write minimal code to pass the test
  → Verify test PASSES

STEP 2: Tests Must Pass Gate (TDD)
  → Run full test suite
  → ALL tests must pass before task is complete
  → If any test fails, fix code, not tests
```

---

## TODOs

- [x] 1. **Investigate EPUB data flow** — `quick`

  **What to do**:
  - Confirm where `## text` conversion happens (extractor vs MarkdownGenerator)
  - Check if `_clean_html` at line 162 is the source
  - Verify existing EPUB test file structure
  - Record findings before implementing fix

  **Must NOT do**:
  - Do NOT modify any code yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Investigation only, no code changes
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 2, 3, 4)
  - **Blocks**: Task 5 (EPUB fix implementation)
  - **Blocked By**: None

  **References**:
  - `src/opp/extractors/epub.py:161-162` - `_clean_html` h1-h6 conversion
  - `src/opp/markdown.py:14-16` - headings_paragraphs filtering
  - `tests/extractors/test_epub.py` (if exists) - existing test structure

  **Acceptance Criteria**:
  - [ ] Clear documentation of data flow (extractor → ParagraphData → MD Generator)
  - [ ] Confirmed whether `## text` is created in extractor or downstream

- [x] 2. **Investigate PDF library and TOC API** — `quick`

  **What to do**:
  - Check `src/opp/extractors/pdf.py` imports to confirm fitz is already used
  - Test `fitz.Document.get_toc()` API behavior on sample PDFs
  - Find/create test PDF with bookmarks
  - Document expected return format from `get_toc()`

  **Must NOT do**:
  - Do NOT modify any code yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Investigation only, API research
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 1, 3, 4)
  - **Blocks**: Task 6 (PDF fix implementation)
  - **Blocked By**: None

  **References**:
  - `src/opp/extractors/pdf.py:6` - `import fitz`
  - `batch_test/` - test PDFs if available

  **Acceptance Criteria**:
  - [ ] fitz already imported (no new dependency needed)
  - [ ] `get_toc()` return format documented: `[[level, title, page], ...]`
  - [ ] Test PDF with bookmarks identified or created

- [x] 3. **Investigate PPTX TITLE shape mapping** — `quick`

  **What to do**:
  - Examine `src/opp/extractors/pptx.py` line 77: `shape.shape_type.name`
  - Check what shape types exist for PPTX (TITLE, BODY, SUBTITLE, etc.)
  - Find/create test PPTX with known TITLE shapes
  - Confirm SUBTITLE handling (level=2 or level=None?)

  **Must NOT do**:
  - Do NOT modify any code yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Investigation only
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 1, 2, 4)
  - **Blocks**: Task 7 (PPTX fix implementation)
  - **Blocked By**: None

  **References**:
  - `src/opp/extractors/pptx.py:67-79` - `extract_shapes` method
  - `batch_test/` - test PPTX files if available

  **Acceptance Criteria**:
  - [ ] TITLE shape confirmed to have level=None (current bug)
  - [ ] SUBTITLE shape type identified (if exists)
  - [ ] Test PPTX with TITLE shapes found or created

- [x] 4. **Investigate IPYNB cell level semantics** — `quick`

  **What to do**:
  - Examine `src/opp/extractors/ipynb.py` lines 43-50 for markdown cell handling
  - Check if notebook cell nesting is relevant (notebook v4+ has cell hierarchy)
  - Confirm root-level = level=1 semantics
  - Check existing tests for IPYNB extraction

  **Must NOT do**:
  - Do NOT modify any code yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Investigation only
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 1, 2, 3)
  - **Blocks**: Task 8 (IPYNB fix implementation)
  - **Blocked By**: None

  **References**:
  - `src/opp/extractors/ipynb.py:43-50` - markdown cell extraction
  - `tests/extractors/test_ipynb.py` (if exists)

  **Acceptance Criteria**:
  - [ ] Current level=0 confirmed as bug
  - [ ] Root-level markdown cells should have level=1
  - [ ] Code cells should remain unchanged

- [x] 5. **Fix EPUB extractor heading extraction** — `deep`

  ### DD Vibe Workflow (UTDD → ATDD → TDD)

  **STEP 0: Write Test FIRST** (UTDD)
  - Write test file: `tests/extractors/test_epub_headings.py`
  - Test must assert:
    - Given EPUB with h1-h6 → expect ParagraphData with level=1-6, style="Heading N"
    - Given EPUB with body text → expect ParagraphData with level=None, style="Normal"
    - Given EPUB with h1+h2 → expect paragraphs[0].level==1 AND paragraphs[1].level==2
  - Run test → MUST FAIL before implementation

  **STEP 1: Implement** (ATDD)
  - Modify `_extract_chapters` in `src/opp/extractors/epub.py` (around line 103-141)
  - Parse h1-h6 tags in `_clean_html` and return structured data instead of flat text
  - Set `ParagraphData.style="Heading N"` and `level=N` for headings
  - Set `style="Normal"` and `level=None` for body text
  - DO NOT convert h1-h6 to `## text` markdown - return raw text instead

  **STEP 2: Tests Must Pass Gate** (TDD)
  - Run `pytest tests/extractors/test_epub_headings.py -v`
  - ALL assertions must pass
  - If fails: fix implementation, not tests

  **Must NOT do**:
  - Do NOT convert headings to `## text` markdown syntax in extractor
  - Do NOT lose footnote markers `[[footnote]]`
  - Do NOT modify `_clean_html` to output anything other than clean text

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding of EPUB structure and careful parsing
  - **Skills**: []
    - No specific skills needed for this straightforward fix

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 6, 7, 8)
  - **Blocks**: Final Verification
  - **Blocked By**: Task 1 (EPUB data flow investigation)

  **References**:
  - `src/opp/extractors/epub.py:103-141` - `_extract_chapters` method to modify
  - `src/opp/extractors/epub.py:143-177` - `_clean_html` method
  - `src/opp/utils/dataclasses.py` - ParagraphData definition

  **Acceptance Criteria** (ATDD - with assertions):
  - [ ] `→ assert h1.tag creates ParagraphData with level=1, style="Heading 1"`
  - [ ] `→ assert h2.tag creates ParagraphData with level=2, style="Heading 2"`
  - [ ] `→ assert h6.tag creates ParagraphData with level=6, style="Heading 6"`
  - [ ] `→ assert non-heading paragraphs have level=None, style="Normal"`
  - [ ] `→ assert footnote markers [[footnote]] preserved in text`

  **QA Scenarios** (BDD - Given-When-Then):

  ```
  Given: EPUB with h1, h2, body text
    When: Running extractor on test EPUB
    Then: paragraphs[0].level → assert equals 1
    And: paragraphs[0].style → assert contains "Heading 1"
    And: paragraphs[1].level → assert equals 2
    And: body paragraphs → assert level is None
    Evidence: .sisyphus/evidence/task-5-epub-headings.txt

  Given: EPUB with empty heading <h3></h3> or <h3/>
    When: Running extractor
    Then: ParagraphData → assert level==3 and style=="Heading 3" and text==""
    Evidence: .sisyphus/evidence/task-5-epub-empty-heading.txt

  Given: EPUB with footnote <span role="doc-noteref">[1]</span>
    When: Running extractor
    Then: text → assert contains "[[footnote]]"
    Evidence: .sisyphus/evidence/task-5-epub-footnote.txt
  ```

- [x] 6. **Fix PDF extractor TOC extraction** — `deep`

  ### DD Vibe Workflow (UTDD → ATDD → TDD)

  **STEP 0: Write Test FIRST** (UTDD)
  - Write test file: `tests/extractors/test_pdf_toc.py`
  - Test must assert:
    - Given PDF with bookmarks → expect TOC ParagraphData with level=1-6
    - Given PDF with no bookmarks → expect no TOC ParagraphData added
    - Given PDF with 2-level TOC → expect level=1 for top-level, level=2 for nested
  - Run test → MUST FAIL before implementation

  **STEP 1: Implement** (ATDD)
  - Add `extract_toc` method to `PDFExtractor` in `src/opp/extractors/pdf.py`
  - Call `doc.get_toc()` to get bookmarks
  - Convert TOC entries to ParagraphData with level=1-N and style="Heading N"
  - Page numbers from TOC: use `fitz.open(input_path)` and page index
  - Merge TOC paragraphs with existing text paragraphs (preserve reading order)
  - Handle empty TOC gracefully (no bookmarks → return empty list for TOC)

  **STEP 2: Tests Must Pass Gate** (TDD)
  - Run `pytest tests/extractors/test_pdf_toc.py -v`
  - ALL assertions must pass
  - If fails: fix implementation, not tests

  **Must NOT do**:
  - Do NOT add heuristic TOC extraction (only use fitz.get_toc())
  - Do NOT modify text block extraction (only add TOC on top)
  - Do NOT change existing ParagraphData for non-heading text (style=None, level=None)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Needs careful handling of TOC structure and page mapping
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 5, 7, 8)
  - **Blocks**: Final Verification
  - **Blocked By**: Task 2 (PDF library investigation)

  **References**:
  - `src/opp/extractors/pdf.py:25-84` - `extract` method to modify
  - `src/opp/extractors/pdf.py:184-201` - `extract_text_blocks` for pattern reference
  - `src/opp/utils/dataclasses.py` - ParagraphData definition

  **Acceptance Criteria** (ATDD - with assertions):
  - [ ] `→ assert TOC entries have correct level (1 = top-level, 2 = nested, etc.)`
  - [ ] `→ assert TOC entries have correct page number (1-indexed, matching PDF page)`
  - [ ] `→ assert TOC entries are interleaved with text blocks at correct positions`
  - [ ] `→ assert empty TOC (no bookmarks) returns empty list, not error`

  **QA Scenarios** (BDD - Given-When-Then):

  ```
  Given: PDF with 2-level TOC bookmarks ("Chapter 1" at page 1, "Section 1.1" at page 2)
    When: Running extractor on test PDF
    Then: first TOC entry → assert level==1 and text=="Chapter 1"
    And: second TOC entry → assert level==2 and text=="Section 1.1"
    Evidence: .sisyphus/evidence/task-6-pdf-toc.txt

  Given: Plain PDF with no TOC/bookmarks
    When: Running extractor
    Then: no TOC paragraphs → assert were added
    And: existing text blocks → assert are still extracted
    Evidence: .sisyphus/evidence/task-6-pdf-no-toc.txt

  Given: PDF with heading containing special characters `&<>`
    When: Running extractor
    Then: heading text → assert matches (properly escaped)
    Evidence: .sisyphus/evidence/task-6-pdf-special-chars.txt
  ```

- [x] 7. **Fix PPTX extractor TITLE shape mapping** — `deep`

  ### DD Vibe Workflow (UTDD → ATDD → TDD)

  **STEP 0: Write Test FIRST** (UTDD)
  - Write test file: `tests/extractors/test_pptx_title.py`
  - Test must assert:
    - Given PPTX with TITLE shape → expect ParagraphData with level=1, style contains "Heading"
    - Given PPTX with BODY shape → expect ParagraphData with level=None
    - Given PPTX with GROUP containing TITLE → expect TITLE gets level=1
  - Run test → MUST FAIL before implementation

  **STEP 1: Implement** (ATDD)
  - Modify `extract_shapes` in `src/opp/extractors/pptx.py` (lines 67-79)
  - Map `MSO_SHAPE_TYPE.TITLE` to `level=1` and `style="Heading 1"`
  - Map `MSO_SHAPE_TYPE.SUBTITLE` (if exists) to `level=2` and `style="Heading 2"`
  - For other shapes with text: keep `level=None` and original `style=shape_type.name`

  **STEP 2: Tests Must Pass Gate** (TDD)
  - Run `pytest tests/extractors/test_pptx_title.py -v`
  - ALL assertions must pass
  - If fails: fix implementation, not tests

  **Must NOT do**:
  - Do NOT change level for non-TITLE shapes
  - Do NOT remove existing image extraction
  - Do NOT change notes extraction behavior

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Simple mapping change but needs to be precise
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 5, 6, 8)
  - **Blocks**: Final Verification
  - **Blocked By**: Task 3 (PPTX shape investigation)

  **References**:
  - `src/opp/extractors/pptx.py:67-79` - `extract_shapes` method
  - `src/opp/extractors/pptx.py:1-6` - imports (MSO_SHAPE_TYPE)
  - `src/opp/markdown.py:51-61` - `generate_headings` for reference

  **Acceptance Criteria** (ATDD - with assertions):
  - [ ] `→ assert TITLE shape creates ParagraphData with level=1, style contains "Heading 1"`
  - [ ] `→ assert BODY or other non-TITLE shapes have level=None`
  - [ ] `→ assert existing functionality (images, notes) unchanged`

  **QA Scenarios** (BDD - Given-When-Then):

  ```
  Given: PPTX with slide containing TITLE "Introduction"
    When: Running extractor on test PPTX
    Then: ParagraphData with text="Introduction" → assert level==1 and style contains "Heading"
    Evidence: .sisyphus/evidence/task-7-pptx-title.txt

  Given: PPTX with body text shape (not TITLE)
    When: Running extractor
    Then: ParagraphData for body text → assert level is None (not a heading)
    Evidence: .sisyphus/evidence/task-7-pptx-body.txt

  Given: PPTX with grouped shapes including TITLE
    When: Running extractor
    Then: TITLE inside GROUP → assert also gets level=1
    Evidence: .sisyphus/evidence/task-7-pptx-group.txt
  ```

- [x] 8. **Fix IPYNB extractor markdown cell level** — `quick`

  ### DD Vibe Workflow (UTDD → ATDD → TDD)

  **STEP 0: Write Test FIRST** (UTDD)
  - Write test file: `tests/extractors/test_ipynb_level.py`
  - Test must assert:
    - Given IPYNB with markdown cell → expect ParagraphData with level=1
    - Given IPYNB with code cell → expect ParagraphData with level=0, style="Code"
  - Run test → MUST FAIL before implementation

  **STEP 1: Implement** (ATDD)
  - Modify `src/opp/extractors/ipynb.py` line 48: change `level=0` to `level=1`
  - Add comment explaining why (markdown headings at root level = level 1)
  - Ensure code cells remain unchanged (level=0 for code is correct)

  **STEP 2: Tests Must Pass Gate** (TDD)
  - Run `pytest tests/extractors/test_ipynb_level.py -v`
  - ALL assertions must pass
  - If fails: fix implementation, not tests

  **Must NOT do**:
  - Do NOT change code cell handling
  - Do NOT change style="Markdown" (keep as-is)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single line change, low risk
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with 5, 6, 7)
  - **Blocks**: Final Verification
  - **Blocked By**: Task 4 (IPYNB cell investigation)

  **References**:
  - `src/opp/extractors/ipynb.py:43-50` - markdown cell handling
  - `src/opp/markdown.py:14-16` - headings_paragraphs filtering

  **Acceptance Criteria** (ATDD - with assertions):
  - [ ] `→ assert Markdown cells have level=1 (not 0)`
  - [ ] `→ assert Code cells unchanged (level=0, style="Code")`
  - [ ] `→ assert all existing tests pass`

  **QA Scenarios** (BDD - Given-When-Then):

  ```
  Given: Notebook with markdown cell "## Section Title"
    When: Running extractor
    Then: ParagraphData → assert level==1
    And: ParagraphData → assert style=="Markdown"
    Evidence: .sisyphus/evidence/task-8-ipynb-markdown.txt

  Given: Notebook with code cell `print("hello")`
    When: Running extractor
    Then: ParagraphData for code cell → assert level==0 and style=="Code"
    Evidence: .sisyphus/evidence/task-8-ipynb-code.txt
  ```

---

## Final Verification Wave (DD Vibe Compliant)

Each F1-F4 task runs AFTER all T5-T8 STEP 2 gates pass and verifies DD Vibe compliance:

- [x] F1. **Plan Compliance Audit** — `oracle`
  - Read the plan end-to-end. For each "Must Have": verify implementation exists
  - For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found
  - **Verify DD Vibe**: Check each task has STEP 0 (test first), STEP 1 (implement), STEP 2 (test gate)
  - Check evidence files exist in .sisyphus/evidence/

- [x] F2. **Code Quality Review** — `unspecified-high`
  - Run `pytest tests/ -v` and ensure ALL tests pass
  - **Verify DD Vibe**: Review that tests were written FIRST (UTDD compliance)
  - Review changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports

- [x] F3. **Real Manual QA** — `unspecified-high`
  - Execute EVERY Given-When-Then QA scenario from EVERY task
  - Follow exact steps, capture evidence in .sisyphus/evidence/
  - **Verify DD Vibe**: Confirm all scenarios follow Given-When-Then format
  - Test edge cases: empty state, invalid input

- [x] F4. **Scope Fidelity Check** — `deep`
  - For each task: read "What to do", read actual diff (git log/diff)
  - Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep)
  - **Verify DD Vibe**: Confirm STEP 0 → STEP 1 → STEP 2 workflow was followed

---

## Success Criteria

| Format | Success Condition |
|--------|-------------------|
| EPUB | Heading cells have level=1-6, style="Heading N" |
| PPTX | TITLE shapes have level=1, other shapes level=None |
| PDF | TOC items extracted with page numbers into ParagraphData |
| IPYNB | Markdown cells have level=1, code cells unchanged |

---

## Commit Strategy
- Each format fix: separate commit with test
- Message: `fix(extractor): preserve structure for {format}`

---

## Known Limitations

### 1. PPTX: GROUP with TITLE Shape (T7-S3)
- **Issue**: python-pptx cannot programmatically create placeholder shapes with type=TITLE inside a GROUP shape
- **Impact**: T7-S3 QA scenario "GROUP with TITLE → level=1" cannot be programmatically verified
- **Resolution**: Code review verified - `_flatten_group` implementation is correct
  - The method correctly identifies TITLE shapes via `_is_title_shape()` check
  - The method correctly recurses into nested GROUP shapes
  - Library limitation prevents automated test creation, not implementation defect

### 2. EPUB: Empty Heading Tags
- **Issue**: Empty heading tags like `<h3></h3>` or `<h3/>` are now preserved (after fix)
- **Impact**: Previously these were skipped, now they produce `ParagraphData(text="", style="Heading N", level=N)`
- **Resolution**: Fixed in commit `5423f0a` - empty headings now preserved correctly