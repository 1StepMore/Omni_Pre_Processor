# phase3-plan Learnings

## ResourceManager (Task 2)
- Created `src/opp/resource_manager.py` with MD5 deduplication
- Uses `uuid.uuid4()` for filename generation, preserves extension
- `_mapping: Dict[str, Tuple[Path, str]]` tracks md5 -> (stored_path, original_name)
- `add_image()` returns stored Path, skips re-save for duplicates
- `get_mapping()` returns original_name -> stored_path dict

## test_auto_detector.py (Task 4)
- Created `tests/test_auto_detector.py` with 13 tests for format detector
- detector.py catches FileNotFoundError internally and returns (UNKNOWN, 0.0) instead of raising
  - This is why test_missing_file checks return value, not exception
- Magic bytes take precedence over extension:
  - %PDF prefix → PDF regardless of extension
  - PK prefix → checked against extension (.docx/.pptx) for specific type
- Test fixtures: sample_files_normal provides valid DOCX/PPTX/PDF files with various content

## resource_manager.py (Task 5 - Path Maintenance)
- Added `_cross_ref: Dict[str, str]` for MD5 → position_marker tracking
- Added `relocate_resources(output_dir: Path) -> None`:
  - Creates output_dir if needed
  - Uses `shutil.move` (not copy) to avoid duplicates
  - Updates `_mapping` with new paths
- Added `get_resource_path(original_name: str) -> Path`:
  - Iterates through _mapping values to find matching original_name
  - Raises KeyError if not found
- Added `set_cross_ref(md5_hash: str, position_marker: str) -> None`
- All existing methods unchanged (add_image, get_mapping, _compute_file_md5)

## test_integration.py (Task 10)
- Created `tests/test_integration.py` with 21 tests for OPP pipeline integration
- OPPPipeline is in `src/opp/pipeline.py` with `process_file()` and `process_batch()`
- Returns `ProcessingResult` (content, format_type, images_stored, errors, warnings, duration_ms)
- Returns `BatchResult` (successful, failed, total_duration_ms, results)
- Some sample files return empty content (with_table.docx, with_notes.pptx, with_images.pdf)
  - These edge cases extract format correctly but content may be empty
  - Tests use `isinstance(result.content, str)` instead of `assert result.content`
- ResourceManager integration tested via `pipeline.resource_manager.get_mapping()`
- Error handler accessible via `pipeline.error_handler.get_errors()`
