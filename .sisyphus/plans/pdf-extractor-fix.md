# PDF Extractor Fix - Work Plan

## TL;DR

> **Quick Summary**: Fix three bugs in the PDF extractor: (1) Chinese chapter headings like "一、项目背景" not converted to markdown headings, (2) table header row appearing duplicated in markdown output, (3) `extract_toc()` method never called during pipeline execution.
>
> **Deliverables**:
> - Modified `src/opp/extractors/pdf.py` with Chinese heading detection
> - Fixed table extraction to skip duplicate header row
> - Integrated TOC extraction into main extraction flow
>
> **Estimated Effort**: Short (2-3 files, focused changes)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 3 → Task 4

---

## Context

### Original Request
Fix PDF extractor to properly handle:
1. Chinese chapter headings (like "一、项目背景") - currently output as plain text
2. Table data duplication (header row appearing twice in markdown)
3. TOC extraction integration (extract_toc() is never called from pipeline)

### Interview Summary
**Key Discussions**:
- DOCX extractor works correctly because it uses Word's built-in paragraph styles ("Heading 1", "Title", etc.)
- PDF extractor fails because it has no native paragraph styles - text is just raw text blocks
- PDF has `extract_toc()` method but it's never called from the pipeline
- Table bug is at line 151: `rows = extracted` (includes header row) instead of `rows = extracted[1:]`

### Research Findings
- PDF extractor's `extract()` method creates paragraphs with `style=None, level=None` (lines 53-56 in pdf.py)
- `extract_toc()` exists at lines 176-196 but is never called
- Markdown generator needs `level >= 1` to create heading markers (`#`)
- Table duplication: `table.extract()` returns ALL rows including header, but code doesn't skip first row

### Metis Review
**Identified Gaps (addressed)**:
- Chinese heading patterns may include: `"一、"`, `"第X章"`, `"（一）"`, `"1."`, `"1.1"` - need comprehensive regex
- Edge case: 1-row table would become empty after fix
- TOC integration point: should merge with regular paragraphs (dedupe by text)
- Verification: need concrete before/after markdown examples

---

## Work Objectives

### Core Objective
Fix PDF extraction to correctly identify and preserve document structure (headings, tables) when converting to markdown format.

### Concrete Deliverables
- [ ] Chinese chapter headings (`一、`, `第X章`, `1.`, etc.) converted to markdown headings (`#`)
- [ ] Table header not duplicated in markdown output
- [ ] TOC entries (from PDF bookmarks) properly merged into extraction results

### Definition of Done
- [ ] `batch_files/AI赋能公版儿童绘本创业方向建议书.pdf` output contains `# 一、项目背景` format headings
- [ ] Table markdown has no duplicate header row
- [ ] `pytest tests/extractors/test_pdf_toc.py` passes
- [ ] No regression in existing PDF extraction tests

### Must Have
- Regex pattern covering common Chinese heading formats
- Table fix that handles 1-row edge case
- TOC merging that doesn't duplicate content

### Must NOT Have (Guardrails)
- No new dependencies added
- No modification to DOCX/EPUB/HTML extractors
- No changes to dataclasses.py structure
- No AI/ML-based heading detection
- No configuration file changes

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (tests-after for PDF extractor)
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - fixes):
├── Task 1: Fix table duplication bug [quick]
├── Task 2: Add Chinese heading detection method [quick]
└── Task 3: Integrate TOC extraction into extract() [quick]

Wave 2 (After Wave 1 - integration/QA):
├── Task 4: Run PDF extractor tests [quick]
└── Task 5: Verify with sample PDF [quick]
```

### Dependency Matrix

- **Task 1**: - - Task 2, Task 3
- **Task 2**: - - Task 4
- **Task 3**: - - Task 4
- **Task 4**: Task 1, Task 2, Task 3 - Task 5
- **Task 5**: Task 4 -

> Wave 1 tasks can run in parallel (no dependencies between them)
> Wave 2 tasks depend on all Wave 1 tasks completing

---

## TODOs

---

- [x] 1. Fix table duplication bug in `detect_tables()`

  **What to do**:
  - Locate line 151 in `src/opp/extractors/pdf.py`
  - Change `rows = extracted` to `rows = extracted[1:]` to skip header row
  - Add edge case check: if `len(extracted) <= 1`, don't add table (no data rows)

  **Must NOT do**:
  - Don't change table header extraction logic
  - Don't modify other extractors

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple one-line fix, predictable outcome
  - **Skills**: []
    - Not needed for simple line change

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4, Task 5
  - **Blocked By**: None (can start immediately)

  **References**:

  > Pattern to follow from DOCX extractor (`src/opp/extractors/docx.py:94-99`):
  > ```python
  > headers = [cell.text.strip() for cell in first_row.cells]
  > for row in table.rows[1:]:  # Skip header row
  >     rows.append([cell.text.strip() for cell in row.cells])
  > ```

  > Why each reference matters:
  > - `docx.py:94-99` shows the CORRECT pattern for skipping header rows - DOCX extractor iterates from row 1 onwards, not row 0

  **Acceptance Criteria**:

  **If tests enabled**:
  - [ ] Test file updated: `tests/extractors/test_pdf_tables.py`
  - [ ] `pytest tests/extractors/test_pdf_tables.py -v` → PASS

  **QA Scenarios**:

  ```
  Scenario: Table with multiple data rows
    Tool: Bash
    Preconditions: PDF with table (header + 3 data rows)
    Steps:
      1. Run: python -c "from src.opp.extractors.pdf import PDFExtractor; e = PDFExtractor(); r = e.extract('batch_files/AI赋能公版儿童绘本创业方向建议书.pdf')"
      2. Check: len(r.tables[0].rows) == 3 (not 4)
    Expected Result: Only 3 data rows, no duplicate header
    Failure Indicators: len(rows) == 4 means header still duplicated
    Evidence: .sisyphus/evidence/task-1-table-multi-row.txt

  Scenario: Table with only 1 row (edge case)
    Tool: Bash
    Preconditions: PDF with table (header + 1 data row)
    Steps:
      1. Run same command as above
      2. Check: len(r.tables) == 0 OR (len(r.tables[0].rows) == 1)
    Expected Result: Table not added if only header row, or single data row preserved
    Failure Indicators: Empty rows array or index error
    Evidence: .sisyphus/evidence/task-1-table-single-row.txt
  ```

---

- [x] 2. Add Chinese heading detection method

  **What to do**:
  - In `src/opp/extractors/pdf.py`, add new method `_detect_heading_level(text: str) -> Optional[int]`
  - Method should use regex to detect Chinese heading patterns:
    - `"^[一二三四五六七八九十百千]+、" → level 1 (一、二、三、)
    - `"^第[一二三四五六七八九十百千万\\d]+章"` → level 1 (第一章)
    - `"^第[一二三四五六七八九十百千万\\d]+节"` → level 2 (第一节)
    - `"^\\d+\\."` → level 1 (1. 2. 3.)
    - `"^\\d+\\.\\d+"` → level 2 (1.1 2.1)
  - Return `None` if no pattern matches
  - Call this method in `extract()` when creating `ParagraphData`

  **Must NOT do**:
  - Don't add new dependencies (use `re` module, already available)
  - Don't hardcode extensive list - use regex groups
  - Don't modify other extractors

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard pattern matching, straightforward implementation
  - **Skills**: []
    - Not needed for regex implementation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 4, Task 5
  - **Blocked By**: None (can start immediately)

  **References**:

  > Reference from HTML extractor heading detection (`src/opp/extractors/html.py:204-209`):
  > ```python
  > if line.startswith("#"):
  >     match = re.match(r'^(#{1,6})\s+(.*)', line)
  >     if match:
  >         level = len(match.group(1))
  > ```

  > Reference from DOCX extractor heading level extraction (`src/opp/extractors/docx.py:62-67`):
  > ```python
  > if style_name and style_name.startswith("Heading"):
  >     try:
  >         level = int(style_name.replace("Heading ", "").replace("Heading", ""))
  >     except ValueError:
  >         level = 1
  > ```

  > Why each reference matters:
  > - `html.py:204-209` shows OPP's standard regex pattern for heading detection
  > - `docx.py:62-67` shows OPP's standard pattern for extracting heading level from style name

  **Acceptance Criteria**:

  **If tests enabled**:
  - [ ] Test file created: `tests/extractors/test_pdf_headings.py`
  - [ ] `pytest tests/extractors/test_pdf_headings.py -v` → PASS

  **QA Scenarios**:

  ```
  Scenario: Chinese numbered headings detected correctly
    Tool: Bash
    Preconditions: Text blocks with Chinese heading patterns
    Steps:
      1. Run: python -c "from src.opp.extractors.pdf import PDFExtractor; e = PDFExtractor(); level = e._detect_heading_level('一、项目背景')"
      2. Assert: level == 1
      3. Run: level = e._detect_heading_level('第一节')
      4. Assert: level == 2
    Expected Result: Correct level returned for each pattern
    Failure Indicators: Returns None or wrong level
    Evidence: .sisyphus/evidence/task-2-chinese-heading.txt

  Scenario: Non-heading text returns None
    Tool: Bash
    Preconditions: Regular paragraph text
    Steps:
      1. Run: python -c "from src.opp.extractors.pdf import PDFExtractor; e = PDFExtractor(); level = e._detect_heading_level('这是一个普通的段落文本')"
      2. Assert: level is None
    Expected Result: None returned for non-heading text
    Failure Indicators: Returns a number instead of None
    Evidence: .sisyphus/evidence/task-2-normal-text.txt
  ```

---

- [x] 3. Integrate TOC extraction into main extraction flow

  **What to do**:
  - In `PDFExtractor.extract()`, after extracting text blocks:
    1. Call `self.extract_toc(input_path)` to get TOC entries
    2. Merge TOC entries with regular paragraphs, deduping by text content
    3. Prepend TOC entries to paragraph list (TOC at beginning of document)
  - TOC entries have `level` and `style` set, so they will be rendered as headings

  **Must NOT do**:
  - Don't add new field to `ExtractionResult` - just merge paragraphs
  - Don't call `extract_toc()` twice
  - Don't let TOC duplicate content already in paragraphs

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple merge operation, straightforward logic
  - **Skills**: []
    - Not needed for list merging

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 4, Task 5
  - **Blocked By**: None (can start immediately)

  **References**:

  > Reference for TOC merge pattern - none exists in codebase. This is a new integration point.

  > Key insight: `extract_toc()` returns `List[ParagraphData]` with `level` and `style` already set. These should be prepended to the regular paragraphs list.

  **Acceptance Criteria**:

  **If tests enabled**:
  - [ ] Test file updated: `tests/extractors/test_pdf_toc.py`
  - [ ] `pytest tests/extractors/test_pdf_toc.py -v` → PASS

  **QA Scenarios**:

  ```
  Scenario: TOC entries merged with paragraphs
    Tool: Bash
    Preconditions: PDF with TOC entries and regular content
    Steps:
      1. Run: python -c "from src.opp.extractors.pdf import PDFExtractor; e = PDFExtractor(); r = e.extract('batch_files/AI赋能公版儿童绘本创业方向建议书.pdf')"
      2. Check: r.paragraphs[0].style starts with "Heading"
      3. Check: r.paragraphs[0].level is not None
    Expected Result: First paragraph is a heading (from TOC)
    Failure Indicators: First paragraph has style=None, level=None
    Evidence: .sisyphus/evidence/task-3-toc-merge.txt

  Scenario: No duplicate content when TOC entries match body
    Tool: Bash
    Preconditions: PDF where TOC title matches body text
    Steps:
      1. Run same command
      2. Check: No paragraph text appears twice in r.paragraphs
    Expected Result: Deduplication works correctly
    Failure Indicators: Duplicate paragraphs
    Evidence: .sisyphus/evidence/task-3-no-duplicate.txt
  ```

---

- [x] 4. Run PDF extractor tests

  **What to do**:
  - Run existing PDF extractor tests to ensure no regression
  - Run new tests for the fixes
  - All tests should pass

  **Must NOT do**:
  - Don't modify existing tests to make them pass
  - If tests fail, fix the implementation, not the tests

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Running tests is simple verification
  - **Skills**: []
    - Not needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (must run after Tasks 1, 2, 3 complete)
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: Task 5
  - **Blocked By**: Tasks 1, 2, 3

  **References**:

  > Test files in codebase:
  > - `tests/extractors/test_pdf_extractor.py` - existing PDF tests
  > - `tests/extractors/test_pdf_toc.py` - TOC tests (may exist)
  > - `tests/extractors/test_pdf_tables.py` - table tests (may exist)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: All PDF extractor tests pass
    Tool: Bash
    Preconditions: All PDF test files in place
    Steps:
      1. Run: pytest tests/extractors/test_pdf*.py -v
    Expected Result: All tests PASS (0 failures)
    Failure Indicators: Any test FAIL
    Evidence: .sisyphus/evidence/task-4-test-results.txt
  ```

---

- [x] 5. Verify with sample PDF output

  **What to do**:
  - Extract sample PDF to markdown
  - Verify output contains proper markdown headings
  - Verify table output has no duplicate header

  **Must NOT do**:
  - Don't manually edit the output
  - Don't assume - verify with evidence

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple verification task
  - **Skills**: []
    - Not needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (must run after Task 4)
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: None (final task)
  - **Blocked By**: Task 4

  **References**:

  > Sample file: `batch_files/AI赋能公版儿童绘本创业方向建议书.pdf`
  > Output location: `batch_files_converted/AI赋能公版儿童绘本创业方向建议书.md`

  **Acceptance Criteria**:
  - [ ] Output file contains `# 一、项目背景` format headings
  - [ ] Table in output has no duplicate header row

  **QA Scenarios**:

  ```
  Scenario: Sample PDF converted to markdown correctly
    Tool: Bash
    Preconditions: Sample PDF exists
    Steps:
      1. Run: python -m opp --target-format=md batch_files/AI赋能公版儿童绘本创业方向建议书.pdf --output-dir batch_files_converted
      2. Read: batch_files_converted/AI赋能公版儿童绘本创业方向建议书.md
      3. Check: grep -E "^# " batch_files_converted/AI赋能公版儿童绘本创业方向建议书.md | head -10
    Expected Result: Markdown headings present (lines starting with #)
    Failure Indicators: No lines starting with #
    Evidence: .sisyphus/evidence/task-5-md-output.txt

  Scenario: Table has no duplicate header
    Tool: Bash
    Preconditions: Sample PDF converted
    Steps:
      1. Read: batch_files_converted/AI赋能公版儿童绘本创业方向建议书.md
      2. Check: grep -A 5 "^|" | head -20
    Expected Result: Table header appears once, not twice
    Failure Indicators: Header appears twice in table
    Evidence: .sisyphus/evidence/task-5-table-check.txt
  ```

---

## Final Verification Wave

> After ALL implementation tasks complete, 4 review agents run in PARALLEL:

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `tsc --noEmit` + linter + `bun test`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep).
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `fix(pdf): handle Chinese headings and table duplication`
  - Files: `src/opp/extractors/pdf.py`
  - Pre-commit: `pytest tests/extractors/test_pdf*.py -v`

---

## Success Criteria

### Verification Commands
```bash
# All PDF tests pass
pytest tests/extractors/test_pdf*.py -v

# Sample PDF converts correctly
python -m opp --target-format=md batch_files/AI赋能公版儿童绘本创业方向建议书.pdf --output-dir batch_files_converted

# Check headings in output
grep -E "^# " batch_files_converted/AI赋能公版儿童绘本创业方向建议书.md | head -5
```

### Final Checklist
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] All tests pass
- [x] Sample PDF output verified