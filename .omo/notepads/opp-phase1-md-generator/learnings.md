# OPP Phase 1 - MarkdownGenerator TDD RED Phase

## Task Completed
Created `src/opp/markdown.py` skeleton for MarkdownGenerator class.

## Pattern Followed
- Followed OPP extractor patterns from `src/opp/extractors/base.py` and `src/opp/extractors/docx.py`
- Used same import structure: `from opp.utils.dataclasses import ...`

## Verification
- Python syntax check: `python3 -m py_compile` → PASSED
- File created with all 5 method signatures raising NotImplementedError

## Methods Defined
1. `generate(result: ExtractionResult) -> str`
2. `generate_to_file(result: ExtractionResult, output_path: Path) -> None`
3. `generate_headings(paragraphs: List[ParagraphData]) -> str`
4. `generate_lists(paragraphs: List[ParagraphData]) -> str`
5. `generate_tables_md(tables: List[TableData]) -> str`

## Next Step
Implement GREEN phase - actual logic for methods.

---

## Test File Created (2025-05-09)
Created `tests/test_md_generator.py` for RED phase TDD.

### Test Structure
- Class: `TestMarkdownGenerator`
- 17 test methods using inline ParagraphData/TableData (no fixtures)
- Import: `from opp.markdown.generator import MarkdownGenerator` (fails as expected)

### Tests Coverage
**Headings (6 tests):**
- test_generate_headings_h1_h6 - H1-H6 levels
- test_generate_headings_numbered - numbered headings
- test_generate_headings_custom_style_mapping - custom style mapping
- test_generate_headings_single_level - single heading
- test_generate_headings_empty_level - skip empty level
- test_generate_headings_deep_level - level > 6 degrade to H6

**Lists (6 tests):**
- test_generate_lists_ordered - ordered list
- test_generate_lists_unordered - unordered list
- test_generate_lists_nested - nested/mixed lists
- test_generate_lists_single_item - single item
- test_generate_lists_empty_items - skip empty items
- test_generate_lists_deep_nesting - > 10 levels degrade

**Tables (5 tests):**
- test_generate_tables_md_standard - standard table
- test_generate_tables_md_alignment - alignment spec
- test_generate_tables_md_header_detection - header detection
- test_generate_tables_md_single_cell - 1x1 table
- test_generate_tables_md_wide - > 10 columns

### Verification
- `pytest tests/test_md_generator.py -v` → ModuleNotFoundError (expected RED)
