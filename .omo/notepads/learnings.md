# Task 11 CLI Integration Learnings

## Task Summary
Extended CLI in `src/opp/cli.py` to support Phase 3 features.

## What Was Done
1. Created `src/opp/cli.py` with Phase 3 CLI flags:
   - `--detect-format`: Auto-detect file format before processing
   - `--resource-dir`: Directory for storing extracted resources
   - `--report`: Report generation (html/text)
   - `--batch`: Enable batch processing mode
   - Added progress display and statistics output

2. LSP Diagnostics: 2 hints (unused parameters) but no errors

## Key Decisions
- Used argparse standard library for CLI parsing
- Stats dict includes `duration_seconds: 0.0` to satisfy type checker
- No module-level docstrings per AI slop remover rules

## Issues Encountered
- `time` module was incorrectly passed as timestamp to ErrorContext (needed `datetime.now()`)
- Duration (float) vs int stats values required explicit type initialization

## Notes
- CLI currently stubs `process_file()` since pipeline.py wasn't available at creation
- Integration with OPPPipeline will occur when pipeline.py is ready (T12 dependency)
## Task: CSVExtractor TDD RED Tests

## What Was Done
- Created `tests/test_csv_extractor.py` with 23 test cases:
  - 10 Normal cases (UTF-8, tab-separated, empty values, etc.)
  - 5 Boundary cases (10,001 rows, inconsistent columns, etc.)
  - 8 Exception cases (invalid encoding, malformed CSV, etc.)

## Key Decisions
- Followed structure from `test_docx_extractor.py` as reference
- Used pytest fixtures (csv_files_normal, csv_files_boundary, csv_files_error) to create test CSV files
- All tests FAIL initially (as expected for TDD RED phase)
- CSVExtractor validates .tsv as invalid extension (ValidationError) - test expectation correct

## Issues Encountered
- Import error: ModuleNotFoundError for 'openpyxl' when running tests
  - Fixed by using `.venv` instead of `.venv312` which had incomplete pip
- Tests show TypeError with `NoneType has no len()` in `_read_csv_with_encoding`
  - This is expected RED phase - implementation needs fixing

## Test Results
- 18 FAILED (RED phase - expected)
- 5 PASSED (FileNotFoundError, CorruptedFileError, ValidationError cases + supported_extensions)
- Total: 23 test cases

## Notes
- CSVExtractor uses `sep=None` which auto-detects separator but may cause issues
- Tab-separated test expects ValidationError since .tsv not in supported_extensions
- Large file test (10001 rows) expects warning about performance
