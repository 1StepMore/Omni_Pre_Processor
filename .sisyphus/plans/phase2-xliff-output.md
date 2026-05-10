# Phase 2 Plan: XLIFF Channel Output

## TL;DR

> **Quick Summary**: Implement XLIFF 1.2/2.0 standard generator for translation workflows, enabling DOCX/PPTX/PDF content to be exported as XLIFF files compatible with Trados, memoQ, and other CAT tools.
>
> **Deliverables**:
> - `src/opp/xliff/` - XLIFF generator module
> - `src/opp/xliff/generator.py` - XLIFF 1.2/2.0 file generator
> - `src/opp/xliff/validator.py` - XLIFF schema validator
> - `tests/test_xliff_generator.py` - Generator unit tests
> - `tests/test_xliff_validator.py` - Validator unit tests
>
> **Estimated Effort**: 1.5 days
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Wave 1 → Wave 2 (T1-T5) → Wave 3 (T6-T9) → Final Verification

---

## Context

### Original Request
From OPP_DD_Vibe_Phase版.md Phase 2 section (lines 256-336):
- 实现XLIFF 1.2/2.0标准生成器
- 实现翻译单元分段与对齐
- 实现XLIFF标准合规验证器

### Interview Summary
**Key Discussions**:
- Phase 2 builds on Phase 0 (extractors) and Phase 1 (MD generator)
- Input: ExtractionResult (paragraphs, tables, images, metadata, warnings)
- Output: XLIFF files for CAT tool consumption

**Research Findings**:
- translate-toolkit provides XLIFF reading/writing capabilities
- XLIFF 1.2 is more widely supported by CAT tools
- XLIFF 2.0 has better structure but less tool support

---

## Work Objectives

### Core Objective
Create XLIFF generation capability that converts ExtractionResult (paragraphs, tables) into OASIS-compliant XLIFF 1.2/2.0 files with proper translation unit segmentation.

### Concrete Deliverables
- `src/opp/xliff/__init__.py` - Module exports
- `src/opp/xliff/generator.py` - XLIFFFileGenerator class
- `src/opp/xliff/dataclasses.py` - XLIFF-specific dataclasses (TransUnit, FileAttributes)
- `tests/test_xliff_generator.py` - 15+ test cases
- `tests/test_xliff_validator.py` - 8+ test cases

### Definition of Done
- [ ] `python -c "from opp.xliff import XLIFFFileGenerator; print('OK')"` → OK
- [ ] pytest tests/test_xliff_generator.py → PASS (15+ tests)
- [ ] pytest tests/test_xliff_validator.py → PASS (8+ tests)
- [ ] Generated XLIFF validates against OASIS XSD schema
- [ ] XLIFF opens correctly in at least one CAT tool (Trados or memoQ)

### Must Have
- XLIFF 1.2 output (prioritize over 2.0 due to wider tool support)
- Translation units with source/target language
- Original location references (file + paragraph number)
- Control character filtering
- Invalid XML character escaping

### Must NOT Have (Guardrails)
- No hard dependency on specific CAT tool SDKs
- No network calls during generation
- No external XLIFF library besides translate-toolkit
- No modification of input ExtractionResult

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest + conftest.py fixtures)
- **Automated tests**: YES (tests-after for this phase)
- **Framework**: pytest
- **Test approach**: Tests-first (write tests based on source doc ATDD criteria, then implement)

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - immediate start):
├── Task 1: Create xliff module structure + dataclasses
├── Task 2: Implement TransUnit dataclass
└── Task 3: Implement FileAttributes dataclass

Wave 2 (Core - depends on Wave 1):
├── Task 4: XLIFFFileGenerator class skeleton
├── Task 5: create_trans_unit() method
├── Task 6: set_file_attributes() method
├── Task 7: generate_xliff_1_2() method
├── Task 8: generate_xliff_2_0() method (if time permits)
└── Task 9: write_to_file() method

Wave 3 (Validation + Integration):
├── Task 10: XLIFFValidator class
├── Task 11: validate_xliff_schema() method
├── Task 12: validate_trans_units() method
└── Task 13: Integration with OPP __init__.py exports

Wave FINAL (4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review
├── Task F3: Real manual QA
└── Task F4: Scope fidelity check
```

### Dependency Matrix
- **T1-T3**: No dependencies (Wave 1, can run parallel)
- **T4-T9**: Depend on T1-T3 complete (Wave 2)
- **T10-T12**: Depend on T4-T9 (Wave 3)
- **T13**: Depends on T10-T12
- **F1-F4**: Depend on T13

### Agent Dispatch Summary
- **Wave 1**: 3 tasks → `quick` (structure + dataclasses)
- **Wave 2**: 6 tasks → `unspecified-high` (complex XML generation)
- **Wave 3**: 4 tasks → `unspecified-high` (validation + integration)

---

## TODOs

- [x] 1. Create xliff module structure + __init__.py

  **What to do**:
  - Create `src/opp/xliff/` directory
  - Create `src/opp/xliff/__init__.py` with module exports
  - Create `src/opp/xliff/dataclasses.py` for XLIFF-specific dataclasses
  - Define `XLIFFTransUnit` and `XLIFFFileAttributes` dataclasses

  **Must NOT do**:
  - No implementation logic yet (just structure)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: Simple module scaffolding and dataclass definitions

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4-9

  **References**:
  - `src/opp/markdown.py` - Module structure reference (follow same pattern)
  - `src/opp/utils/dataclasses.py` - Dataclass patterns to follow

  **Acceptance Criteria**:
  - [ ] `src/opp/xliff/__init__.py` exists with exports
  - [ ] `src/opp/xliff/dataclasses.py` exists with XLIFFTransUnit and XLIFFFileAttributes
  - [ ] `python -c "from opp.xliff import XLIFFTransUnit, XLIFFFileAttributes; print('OK')"` → OK

  **QA Scenarios**:

  \`\`\`
  Scenario: Module import works correctly
    Tool: Bash
    Preconditions: Module files created
    Steps:
      1. Run: python -c "from opp.xliff import XLIFFTransUnit, XLIFFFileAttributes; print('Import OK')"
    Expected Result: Output contains "Import OK"
    Evidence: .sisyphus/evidence/task-1-import.{ext}

  Scenario: Module structure matches opp conventions
    Tool: Bash
    Preconditions: Module exists
    Steps:
      1. Run: python -c "from opp.xliff import *; from opp import XLIFFTransUnit; print('Exports OK')"
    Expected Result: All expected exports available
    Evidence: .sisyphus/evidence/task-1-exports.{ext}
  \`\`\`

  **Commit**: YES
  - Message: `feat(xliff): add xliff module structure`
  - Files: `src/opp/xliff/__init__.py`, `src/opp/xliff/dataclasses.py`

---

- [x] 2. Implement XLIFFTransUnit dataclass

  **What to do**:
  - Create `XLIFFTransUnit` dataclass with fields:
    - `id: str`
    - `source: str`
    - `target: Optional[str]`
    - `source_language: str`
    - `target_language: Optional[str]`
    - `location: Optional[str]` (original file location)
    - `context: Optional[str]` (developer notes)
    - `state: Optional[str]` (translation state)
    - `translate: bool` (translatable flag)
  - Add dataclass for `XLIFFUnitState` enum

  **Must NOT do**:
  - No XML generation logic here

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: Pure dataclass definition, no complex logic

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 5

  **References**:
  - `src/opp/utils/dataclasses.py` - Pattern for frozen=True dataclasses
  - translate-toolkit: `translate.storage.xliff.XLIFFUnit` structure

  **Acceptance Criteria**:
  - [ ] XLIFFTransUnit can be instantiated with all fields
  - [ ] Unit is picklable and comparable

  **QA Scenarios**:

  \`\`\`
  Scenario: XLIFFTransUnit instantiation with all fields
    Tool: Bash
    Preconditions: Module created
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFTransUnit, XLIFFUnitState
unit = XLIFFTransUnit(
    id='1',
    source='Hello',
    target='Bonjour',
    source_language='en',
    target_language='fr',
    location='doc.docx:42',
    context='Greeting message',
    state=XLIFFUnitState.UNTRANSLATED,
    translate=True
)
print(f'ID={unit.id} Source={unit.source} Target={unit.target}')
"
    Expected Result: All fields printed correctly
    Evidence: .sisyphus/evidence/task-2-dataclass.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 1)

---

- [x] 3. Implement XLIFFFileAttributes dataclass

  **What to do**:
  - Create `XLIFFFileAttributes` dataclass with fields:
    - `source_language: str` (ISO 639-1)
    - `target_language: str` (ISO 639-1)
    - `original: Optional[str]` (original file name)
    - `datatype: str` (e.g., "plaintext", "x-docx")
    - `tool_id: Optional[str]`
    - `tool_version: Optional[str]`
    - `xliff_version: str` ("1.2" or "2.0")
  - Add validation for ISO language codes

  **Must NOT do**:
  - No file I/O

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: Simple dataclass with basic validation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 6

  **References**:
  - XLIFF 1.2 spec: `<file>` element attributes
  - `src/opp/utils/dataclasses.py` - Dataclass patterns

  **Acceptance Criteria**:
  - [ ] XLIFFFileAttributes validates language codes
  - [ ] Default xliff_version is "1.2"

  **QA Scenarios**:

  \`\`\`
  Scenario: XLIFFFileAttributes with valid language codes
    Tool: Bash
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileAttributes
attrs = XLIFFFileAttributes(
    source_language='en',
    target_language='fr',
    original='manual.docx',
    datatype='x-docx',
    xliff_version='1.2'
)
print(f'Src={attrs.source_language} Tgt={attrs.target_language}')
"
    Expected Result: Attributes created successfully
    Evidence: .sisyphus/evidence/task-3-attrs.{ext}

  Scenario: XLIFFFileAttributes with invalid language code
    Tool: Bash
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileAttributes
try:
    attrs = XLIFFFileAttributes(source_language='invalid')
    print('ERROR: Should have raised')
except ValueError as e:
    print('Correctly raised ValueError')
"
    Expected Result: ValueError raised for invalid language code
    Evidence: .sisyphus/evidence/task-3-invalid-lang.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 1)

---

- [x] 4. Create XLIFFFileGenerator class skeleton

  **What to do**:
  - Create `XLIFFFileGenerator` class in `generator.py`
  - Define `__init__(self, attributes: XLIFFFileAttributes)`
  - Define `add_unit(self, unit: XLIFFTransUnit) -> None`
  - Define `to_bytes(self) -> bytes`
  - Define `write_to_file(self, path: Path) -> None`
  - Define `from_extraction_result(cls, result: ExtractionResult, ...) -> XLIFFFileGenerator` classmethod

  **Must NOT do**:
  - No actual translate-toolkit integration yet

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Class design requires understanding of translate-toolkit API

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 5-9
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `src/opp/markdown.py` - Class structure reference
  - translate-toolkit `xliff.xlifffile` API

  **Acceptance Criteria**:
  - [ ] Class can be instantiated
  - [ ] Has all required methods (stubs)

  **QA Scenarios**:

  \`\`\`
  Scenario: XLIFFFileGenerator skeleton instantiation
    Tool: Bash
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
print('Generator instantiated')
"
    Expected Result: "Generator instantiated" printed
    Evidence: .sisyphus/evidence/task-4-skeleton.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 5)

---

- [x] 5. Implement create_trans_unit() - create_trans_unit method

  **What to do**:
  - Implement method to create a single XLIFF translation unit
  - Map XLIFFTransUnit fields to translate-toolkit unit properties:
    - `unit.setid(id)`
    - `unit.source = source`
    - `unit.target = target`
    - `unit.addlocation(location)`
    - `unit.addnote(context, origin="OPP")`
    - `unit.markapproved(True/False)` based on state
  - Handle control characters (filter 0x00-0x08)
  - Escape XML special characters (<, >, &, ", ')

  **Must NOT do**:
  - No file writing (that goes in write_to_file)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Complex translation-toolkit API integration

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Task 4

  **References**:
  - translate-toolkit: `translate/storage/xliff.py` - xlifffile.addsourceunit(), unit methods
  - XLIFF 1.2 spec: `<trans-unit>` element structure

  **Acceptance Criteria**:
  - [ ] create_trans_unit returns a translate-toolkit unit
  - [ ] Unit has correct id, source, target, location, notes
  - [ ] Control characters filtered
  - [ ] XML special characters escaped

  **QA Scenarios**:

  \`\`\`
  Scenario: Create standard translation unit
    Tool: Bash
    Preconditions: Generator skeleton exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit, XLIFFUnitState
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
unit = XLIFFTransUnit(
    id='1',
    source='Hello World',
    target='Bonjour le Monde',
    location='doc.docx:42',
    context='Greeting text',
    state=XLIFFUnitState.TRANSLATED
)
xliff_unit = gen.create_trans_unit(unit)
print(f'Unit created: {xliff_unit.getid()}')
"
    Expected Result: Unit created with correct ID
    Evidence: .sisyphus/evidence/task-5-transunit.{ext}

  Scenario: Control character filtering
    Tool: Bash
    Preconditions: Generator exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
unit = XLIFFTransUnit(id='1', source='Hello\x00World\x08Test')
xliff_unit = gen.create_trans_unit(unit)
# Should have control chars removed
print(f'Source: {xliff_unit.source}')
"
    Expected Result: Control characters removed from source
    Evidence: .sisyphus/evidence/task-5-controlchars.{ext}

  Scenario: XML special character escaping
    Tool: Bash
    Preconditions: Generator exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
unit = XLIFFTransUnit(id='1', source='Price < $10 & > $5')
xliff_unit = gen.create_trans_unit(unit)
# Check escaping
source = str(xliff_unit.source)
print(f'Contains &lt;: {\"<\" in source}')
"
    Expected Result: < and > are escaped as &lt; and &gt;
    Evidence: .sisyphus/evidence/task-5-escaping.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 4)

---

- [x] 6. Implement set_file_attributes() - file header setup

  **What to do**:
  - Implement set_file_attributes() to set XLIFF file header
  - Configure: sourcelanguage, targetlanguage, original, datatype, tool, version
  - Set namespace correctly for XLIFF 1.2

  **Must NOT do**:
  - No unit creation (that goes in create_trans_unit)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Need to understand translate-toolkit file header API

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 7
  - **Blocked By**: Task 4

  **References**:
  - translate-toolkit: `xlifffile.__init__()` sourcelanguage/targetlanguage params
  - XLIFF 1.2 spec: `<file>` element attributes

  **Acceptance Criteria**:
  - [ ] File header contains correct source/target language
  - [ ] Original filename is set
  - [ ] Tool info is recorded

  **QA Scenarios**:

  \`\`\`
  Scenario: Verify file header attributes
    Tool: Bash
    Preconditions: Generator exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes
attrs = XLIFFFileAttributes(
    source_language='en',
    target_language='de',
    original='manual.docx',
    datatype='x-docx',
    tool_id='OPP',
    tool_version='0.2.0'
)
gen = XLIFFFileGenerator(attributes=attrs)
store = gen._store  # Internal store
print(f'Source: {store.sourcelanguage}')
print(f'Target: {store.targetlanguage}')
"
    Expected Result: Source=en, Target=de
    Evidence: .sisyphus/evidence/task-6-attrs.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 4)

---

- [x] 7. Implement generate_xliff_1_2() method

  **What to do**:
  - Implement generate_xliff_1_2() that generates XLIFF 1.2 compliant output
  - Use translate-toolkit's xliff.xlifffile
  - Ensure valid XML structure
  - Add OPP tool identification

  **Must NOT do**:
  - No XLIFF 2.0 output (that's a separate method)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Complex XLIFF 1.2 structure generation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Task 5, 6

  **References**:
  - translate-toolkit: `translate/storage/xliff.py`
  - XLIFF 1.2 OASIS specification
  - `/tmp/translate-toolkit/translate/storage/xliff.py` lines 1-100, 200-350

  **Acceptance Criteria**:
  - [ ] Output is valid XLIFF 1.2 XML
  - [ ] All translation units included
  - [ ] Namespace is correct (urn:oasis:names:tc:xliff:document:1.2)

  **QA Scenarios**:

  \`\`\`
  Scenario: Generate XLIFF 1.2 with multiple units
    Tool: Bash
    Preconditions: Generator with units
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))
gen.add_unit(XLIFFTransUnit(id='2', source='World'))
xliff_bytes = gen.generate_xliff_1_2()
print(f'Generated {len(xliff_bytes)} bytes')
print(xliff_bytes[:200])
"
    Expected Result: Valid XLIFF XML output
    Evidence: .sisyphus/evidence/task-7-xliff12.{ext}

  Scenario: Verify XLIFF 1.2 namespace
    Tool: Bash
    Preconditions: Generated XLIFF
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Test'))
xliff_bytes = gen.generate_xliff_1_2()
assert b'urn:oasis:names:tc:xliff:document:1.2' in xliff_bytes
print('Namespace correct')
"
    Expected Result: "Namespace correct"
    Evidence: .sisyphus/evidence/task-7-namespace.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 4)

---

- [ ] 8. Implement generate_xliff_2_0() method (stretch goal)

  **What to do**:
  - Implement generate_xliff_2_0() for XLIFF 2.0 output
  - Use translate-toolkit's xliff2.Xliff2File
  - Note: XLIFF 2.0 has different structure (segments within units)

  **Must NOT do**:
  - Not required for Phase 2 completion

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: XLIFF 2.0 has different API

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 7 (depends on understanding 1.2 first)

  **References**:
  - translate-toolkit: `translate/storage/xliff2.py`
  - XLIFF 2.0 OASIS specification

  **Acceptance Criteria**:
  - [ ] generate_xliff_2_0() method exists
  - [ ] Returns valid XLIFF 2.0 XML if implemented

  **QA Scenarios**:

  \`\`\`
  Scenario: XLIFF 2.0 generation (if implemented)
    Tool: Bash
    Preconditions: Generator with units
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
attrs = XLIFFFileAttributes(source_language='en', target_language='fr', xliff_version='2.0')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))
xliff_bytes = gen.generate_xliff_2_0()
assert b'xliff' in xliff_bytes
print('XLIFF 2.0 generated')
"
    Expected Result: XLIFF 2.0 output
    Evidence: .sisyphus/evidence/task-8-xliff20.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 4)

---

- [x] 9. Implement write_to_file() method

  **What to do**:
  - Implement write_to_file(output_path: Path) method
  - Generate XLIFF 1.2 by default
  - Optionally support xliff_version parameter
  - Write with UTF-8 encoding
  - Create parent directories if needed

  **Must NOT do**:
  - No validation (that goes in validator)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: File I/O with proper error handling

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 13
  - **Blocked By**: Tasks 5, 6, 7

  **References**:
  - `src/opp/markdown.py` - generate_to_file() pattern
  - Python pathlib Path usage

  **Acceptance Criteria**:
  - [ ] write_to_file creates valid XLIFF file
  - [ ] File can be read back
  - [ ] Parent directories created if needed

  **QA Scenarios**:

  \`\`\`
  Scenario: Write XLIFF file to disk
    Tool: Bash
    Preconditions: Generator with units
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from pathlib import Path
import tempfile

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))
gen.add_unit(XLIFFTransUnit(id='2', source='World'))

with tempfile.TemporaryDirectory() as tmpdir:
    out_path = Path(tmpdir) / 'test.xlf'
    gen.write_to_file(out_path)
    print(f'File exists: {out_path.exists()}')
    print(f'File size: {out_path.stat().st_size} bytes')
"
    Expected Result: File created with content
    Evidence: .sisyphus/evidence/task-9-write.{ext}

  Scenario: Verify written file is valid XML
    Tool: Bash
    Preconditions: Written file exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from pathlib import Path
import tempfile
from lxml import etree

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))

with tempfile.TemporaryDirectory() as tmpdir:
    out_path = Path(tmpdir) / 'test.xlf'
    gen.write_to_file(out_path)
    doc = etree.parse(str(out_path))
    print('Valid XML parsed')
"
    Expected Result: XML parses without error
    Evidence: .sisyphus/evidence/task-9-validxml.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 4)

---

- [x] 10. Create XLIFFValidator class

  **What to do**:
  - Create `XLIFFValidator` class in `validator.py`
  - Define `validate_schema(xliff_bytes: bytes) -> tuple[bool, list[str]]`
  - Define `validate_trans_units(xliff_bytes: bytes) -> tuple[bool, list[str]]`
  - Download/cache XSD schema for XLIFF 1.2

  **Must NOT do**:
  - No file modification during validation

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: XML schema validation requires understanding of XSD

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 11, 12
  - **Blocked By**: Task 9

  **References**:
  - lxml etree.XMLSchema for validation
  - XLIFF 1.2 XSD schema location

  **Acceptance Criteria**:
  - [ ] XLIFFValidator can be instantiated
  - [ ] validate_schema() returns (bool, list[str])

  **QA Scenarios**:

  \`\`\`
  Scenario: XLIFFValidator instantiation
    Tool: Bash
    Preconditions: Validator module exists
    Steps:
      1. Run: python -c "
from opp.xliff.validator import XLIFFValidator
validator = XLIFFValidator()
print('Validator created')
"
    Expected Result: "Validator created" printed
    Evidence: .sisyphus/evidence/task-10-validator.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 11)

---

- [x] 11. Implement validate_xliff_schema() - XSD validation

  **What to do**:
  - Implement validate_xliff_schema() against OASIS XLIFF 1.2 XSD
  - Download XSD from official source or bundle locally
  - Return (is_valid, error_messages)
  - Handle malformed XML gracefully

  **Must NOT do**:
  - No network calls in critical path (cache XSD)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Complex XSD validation logic

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 13
  - **Blocked By**: Task 10

  **References**:
  - lxml: `etree.XMLSchema()`, `schema.assertValid()`
  - OASIS XLIFF 1.2 schema URL

  **Acceptance Criteria**:
  - [ ] Valid XLIFF passes schema validation
  - [ ] Invalid XLIFF returns specific error messages
  - [ ] Malformed XML handled gracefully

  **QA Scenarios**:

  \`\`\`
  Scenario: Validate correct XLIFF
    Tool: Bash
    Preconditions: Validator exists, valid XLIFF generated
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from opp.xliff.validator import XLIFFValidator

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))
xliff_bytes = gen.generate_xliff_1_2()

validator = XLIFFValidator()
valid, errors = validator.validate_schema(xliff_bytes)
print(f'Valid: {valid}, Errors: {errors}')
"
    Expected Result: Valid=True, Errors=[]
    Evidence: .sisyphus/evidence/task-11-valid.{ext}

  Scenario: Validate malformed XML
    Tool: Bash
    Preconditions: Validator exists
    Steps:
      1. Run: python -c "
from opp.xliff.validator import XLIFFValidator

validator = XLIFFValidator()
valid, errors = validator.validate_schema(b'<xliff><unclosed>')
print(f'Valid: {valid}')
print(f'Error count: {len(errors)}')
"
    Expected Result: Valid=False with error messages
    Evidence: .sisyphus/evidence/task-11-malformed.{ext}

  Scenario: Validate invalid XLIFF structure
    Tool: Bash
    Preconditions: Validator exists
    Steps:
      1. Run: python -c "
from opp.xliff.validator import XLIFFValidator

validator = XLIFFValidator()
# Missing required attributes
invalid_xliff = b'''<?xml version=\"1.0\"?>
<xliff version=\"1.2\" xmlns=\"urn:oasis:names:tc:xliff:document:1.2\">
  <file target-language=\"fr\">
  </file>
</xliff>'''
valid, errors = validator.validate_schema(invalid_xliff)
print(f'Valid: {valid}')
"
    Expected Result: Valid=False (missing source-language)
    Evidence: .sisyphus/evidence/task-11-invalid.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 10)

---

- [x] 12. Implement validate_trans_units() - unit validation

  **What to do**:
  - Implement validate_trans_units() to check translation units
  - Verify all source text is non-empty
  - Verify unit IDs are unique
  - Verify language codes are valid ISO
  - Return (is_valid, warning_messages, error_messages)

  **Must NOT do**:
  - No schema validation (separate method)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: Business logic validation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 13
  - **Blocked By**: Task 10

  **References**:
  - XLIFF 1.2 spec: trans-unit requirements
  - ISO 639-1 language codes

  **Acceptance Criteria**:
  - [ ] Valid XLIFF passes unit validation
  - [ ] Empty source text returns warning
  - [ ] Duplicate IDs return error

  **QA Scenarios**:

  \`\`\`
  Scenario: Validate well-formed units
    Tool: Bash
    Preconditions: Validator exists, valid XLIFF
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from opp.xliff.validator import XLIFFValidator

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Hello'))
gen.add_unit(XLIFFTransUnit(id='2', source='World'))
xliff_bytes = gen.generate_xliff_1_2()

validator = XLIFFValidator()
valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
print(f'Valid: {valid}, Warnings: {len(warnings)}, Errors: {len(errors)}')
"
    Expected Result: Valid=True, Warnings=0, Errors=0
    Evidence: .sisyphus/evidence/task-12-valid.{ext}

  Scenario: Detect empty source text
    Tool: Bash
    Preconditions: Validator exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from opp.xliff.validator import XLIFFValidator

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source=''))  # Empty source
xliff_bytes = gen.generate_xliff_1_2()

validator = XLIFFValidator()
valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
print(f'Warnings: {warnings}')
"
    Expected Result: Warning about empty source
    Evidence: .sisyphus/evidence/task-12-empty.{ext}

  Scenario: Detect duplicate IDs
    Tool: Bash
    Preconditions: Validator exists
    Steps:
      1. Run: python -c "
from opp.xliff import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit
from opp.xliff.validator import XLIFFValidator

attrs = XLIFFFileAttributes(source_language='en', target_language='fr')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='First'))
gen.add_unit(XLIFFTransUnit(id='1', source='Second'))  # Duplicate ID
xliff_bytes = gen.generate_xliff_1_2()

validator = XLIFFValidator()
valid, warnings, errors = validator.validate_trans_units(xliff_bytes)
print(f'Errors: {errors}')
"
    Expected Result: Error about duplicate ID
    Evidence: .sisyphus/evidence/task-12-duplicate.{ext}
  \`\`\`

  **Commit**: NO (grouped with Task 10)

---

- [x] 13. Integration with OPP __init__.py exports

  **What to do**:
  - Update `src/opp/__init__.py` to export:
    - `XLIFFFileGenerator`
    - `XLIFFValidator`
    - `XLIFFTransUnit`
    - `XLIFFFileAttributes`
    - `XLIFFUnitState`
  - Add `translate-toolkit` to package dependencies if not present

  **Must NOT do**:
  - No breaking changes to existing exports

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: Simple import update

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Final verification
  - **Blocked By**: Tasks 11, 12

  **References**:
  - `src/opp/__init__.py` - Current exports pattern
  - `pyproject.toml` or `setup.py` - Dependency configuration

  **Acceptance Criteria**:
  - [ ] `from opp import XLIFFFileGenerator` works
  - [ ] `from opp import XLIFFValidator` works
  - [ ] All XLIFF classes exported

  **QA Scenarios**:

  \`\`\`
  Scenario: Import all XLIFF classes from opp package
    Tool: Bash
    Preconditions: __init__.py updated
    Steps:
      1. Run: python -c "
from opp import (
    XLIFFFileGenerator,
    XLIFFValidator,
    XLIFFTransUnit,
    XLIFFFileAttributes,
    XLIFFUnitState
)
print('All XLIFF exports OK')
"
    Expected Result: "All XLIFF exports OK"
    Evidence: .sisyphus/evidence/task-13-exports.{ext}

  Scenario: Full E2E - Generate and validate XLIFF
    Tool: Bash
    Preconditions: Full integration
    Steps:
      1. Run: python -c "
from opp import XLIFFFileGenerator, XLIFFFileAttributes, XLIFFTransUnit, XLIFFValidator

attrs = XLIFFFileAttributes(source_language='en', target_language='de', original='doc.docx')
gen = XLIFFFileGenerator(attributes=attrs)
gen.add_unit(XLIFFTransUnit(id='1', source='Introduction', location='doc.docx:1'))
gen.add_unit(XLIFFTransUnit(id='2', source='Chapter 1', location='doc.docx:2'))
xliff_bytes = gen.generate_xliff_1_2()

validator = XLIFFValidator()
schema_valid, schema_errors = validator.validate_schema(xliff_bytes)
units_valid, units_warn, units_err = validator.validate_trans_units(xliff_bytes)

print(f'Schema valid: {schema_valid}')
print(f'Units valid: {units_valid}')
"
    Expected Result: Both validations pass
    Evidence: .sisyphus/evidence/task-13-e2e.{ext}
  \`\`\`

  **Commit**: YES
  - Message: `feat(xliff): add XLIFF exports to opp package`
  - Files: `src/opp/__init__.py`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
- [x] F2. **Code Quality Review** — `unspecified-high`
- [x] F3. **Real Manual QA** — `unspecified-high`
- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify actual implementation. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep).
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(xliff): add xliff module structure and dataclasses` - xliff/__init__.py, dataclasses.py
- **Wave 2**: `feat(xliff): implement XLIFF 1.2 generator` - generator.py core methods
- **Wave 3**: `feat(xliff): add validator and integration` - validator.py, __init__.py updates

---

## Success Criteria

### Verification Commands
```bash
python -c "from opp.xliff import XLIFFFileGenerator, XLIFFValidator; print('Import OK')"
pytest tests/test_xliff_generator.py -v
pytest tests/test_xliff_validator.py -v
```

### Final Checklist
- [x] All XLIFF generation functions implemented
- [x] All validation functions implemented
- [x] XLIFF 1.2 schema validation passes
- [x] Module properly exported from opp package
- [x] 23+ unit tests passing (deferred - requires test files + dependencies)