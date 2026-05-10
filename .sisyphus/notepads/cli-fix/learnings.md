# CLI Pipeline Integration Fix

## Issue
The CLI accepted `--target-format`, `--source-lang`, `--target-lang`, `--output-dir` flags but never called the pipeline's generation methods. Running `opp --target-format=md file.docx` would detect format but not generate any output.

## Root Cause
The `main()` function in cli.py called `process_file()` which only performed detection, not full extraction + generation. The `OPPPipeline` was imported but never used in the main processing flow.

## Solution

### 1. Modified `ProcessingResult` (pipeline.py)
Added `extraction_result: Optional[ExtractionResult] = None` field to store the full extraction result, enabling the CLI to access it for generation.

### 2. Modified `process_file()` (pipeline.py)
Updated the return statement to include `extraction_result=result` so the ExtractionResult is preserved in ProcessingResult.

### 3. Modified `main()` (cli.py)
Added logic after the `target_format` check that:
1. Creates OPPPipeline with resource_dir
2. Calls `pipeline.process_file(file_path)` to get ProcessingResult with extraction_result
3. Based on `--target-format`:
   - `md` → calls `pipeline.generate_markdown(extraction_result, output_path)`
   - `xlf` → calls `pipeline.generate_xliff(extraction_result, output_path, source_lang, target_lang)`
   - `both` → calls both methods
4. Uses `--output-dir` if specified, otherwise same directory as input

## Key Files Modified
- `src/opp/pipeline.py`: Lines 24 (field), 238 (extraction_result=result)
- `src/opp/cli.py`: Lines 208-261 (new generation logic)

## Verification
The existing CLI tests pass. The diagnostic warnings about unused parameters in `process_file()` are pre-existing issues unrelated to this fix.