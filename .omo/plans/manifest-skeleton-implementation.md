# OPP Manifest + Skeleton Support: Implementation Plan

**Version**: 1.0
**Author**: Implementation Team
**Date**: 2026-05-22
**Target**: Complete manifest.json and skeleton.zip generation support for OPP pipeline

---

## 1. Overview

This plan covers implementing two related features:
1. **manifest.json generation** - JSON metadata describing source files, extraction outputs, and resources
2. **skeleton.zip preservation** - Original OOXML ZIP structure preserved for downstream ORF XLIFF→DOCX/PPTX backfill

### 1.1 Success Criteria

| Criteria | Verification |
|----------|--------------|
| `opp --target-format=md spec.docx` generates `spec_manifest.json` | CLI test |
| `opp --target-format=md spec.docx` generates `spec.skeleton.zip` | CLI test |
| ZIP contains `word/document.xml` (DOCX) or `ppt/presentation.xml` (PPTX) | ZIP content check (DOCX tested in E2E; PPTX tested in unit test T2.3) |
| All existing 479+ tests pass | `pytest tests/ -q` |
| New unit tests for manifest and skeleton | `pytest tests/test_manifest*.py tests/test_skeleton*.py -v` |

---

## 2. Task Breakdown

### Phase 1: manifest.json Generation

#### T1.1: Add Helper Functions to cli.py
**File**: `src/opp/cli.py`
**Lines**: ~1-17 (imports), ~160-220 (process_single_file)
**Status**: ✅ COMPLETED

**Tasks**:
1. Add imports at top of file:
   - `import json` (line ~2)
   - `import hashlib` (line ~3)
   - `from datetime import datetime` (already exists at line 5)

2. Add helper functions before `process_single_file()`:
   ```python
   def _detect_format_from_extension(path: Path) -> str:
       """Detect format type from file extension."""
       ext = path.suffix.lower()
       format_map = {
           ".docx": "DOCX", ".pptx": "PPTX", ".pdf": "PDF",
           ".xlsx": "XLSX", ".html": "HTML", ".xml": "XML",
           ".json": "JSON", ".csv": "CSV", ".epub": "EPUB",
           ".eml": "EML", ".msg": "MSG", ".md": "MARKDOWN",
           ".xlf": "XLIFF", ".xliff": "XLIFF",
       }
       return format_map.get(ext, "UNKNOWN")

   def _compute_file_md5(path: Path) -> str:
       """Compute MD5 hash of file using chunked reading."""
       md5 = hashlib.md5()
       with open(path, "rb") as f:
           for chunk in iter(lambda: f.read(8192), b""):
               md5.update(chunk)
       return md5.hexdigest()

   def _count_xliff_units(xliff_path: Path) -> int:
       """Count trans-unit elements in XLIFF file."""
       import re
       content = xliff_path.read_text(encoding="utf-8")
       return len(re.findall(r'<trans-unit[^>]*>', content))

   def get_opp_version() -> str:
       """Return OPP version string."""
       from opp import __version__
       return __version__
   ```

**Category**: `quick`
**Skills**: `refactor`
**QA**: Run `python -c "from opp.cli import _detect_format_from_extension, _compute_file_md5, _count_xliff_units, get_opp_version; print('OK')"`

---

#### T1.2: Add Manifest Generation to process_single_file()
**File**: `src/opp/cli.py`
**Lines**: 199-214 (after generate_markdown/generate_xliff calls, before return True)

**Tasks**:
1. After line 212 (`get_logger().info(f"Generated: {xliff_path}")`), add manifest generation code with this structure:
   ```python
   manifest = {
       "manifest_version": "1.0",
       "generated_at": datetime.now().isoformat() + "Z",
       "tool": "OPP",
       "tool_version": get_opp_version(),
       "source": {
           "file_path": str(file_path.resolve()),
           "original_filename": file_path.name,
           "format": _detect_format_from_extension(file_path),
           "file_size_bytes": file_path.stat().st_size,
           "file_hash_md5": _compute_file_md5(file_path),
       },
       "extraction": {
           "source_lang": args.source_lang or "en",
           "target_lang": args.target_lang or "en",
           "outputs": {
               "markdown": {
                   "path": str(md_path.relative_to(output_dir)) if md_path.exists() else None,
                   "paragraph_count": len(proc_result.extraction_result.paragraphs) if proc_result.extraction_result else 0,
                   "table_count": len(proc_result.extraction_result.tables) if proc_result.extraction_result else 0,
               },
               "xliff": {
                   "path": str(xliff_path.relative_to(output_dir)) if xliff_path.exists() else None,
                   "trans_unit_count": _count_xliff_units(xliff_path) if xliff_path.exists() else 0,
               }
           },
           "images": [
               {
                   "mime_type": img.mime_type,
                   "width": img.width,
                   "height": img.height,
                   "data_size_bytes": len(img.data),
               }
               for img in (proc_result.extraction_result.images if proc_result.extraction_result else [])
           ],
           "warnings": proc_result.extraction_result.warnings if proc_result.extraction_result else [],
       },
       "resources": {
           "storage_dir": str(args.resource_dir.resolve()) if args.resource_dir else str(Path.cwd() / "resources"),
           "image_count": len(proc_result.extraction_result.images) if proc_result.extraction_result else 0,
       },
   }
   manifest_path = output_dir / f"{base_name}_manifest.json"
   with open(manifest_path, "w", encoding="utf-8") as f:
       json.dump(manifest, f, indent=2, ensure_ascii=False)
   get_logger().info(f"Manifest written: {manifest_path}")
   ```

**Wave Parallel Execution**: T1.1 and T1.2 can be done sequentially in same commit, but T1.3 (tests) should wait.

**Category**: `quick`
**Skills**: `refactor`
**QA**: `python -c "
from pathlib import Path
import json, tempfile
from docx import Document
from opp.pipeline import OPPPipeline

with tempfile.TemporaryDirectory() as tmpdir:
    docx_path = Path(tmpdir) / 'test.docx'
    doc = Document(); doc.add_heading('Test'); doc.save(str(docx_path))
    pipeline = OPPPipeline(Path(tmpdir) / 'resources')
    pipeline.process_file(docx_path)
    output_dir = Path(tmpdir)
    pipeline.generate_markdown(pipeline.process_file(docx_path).extraction_result, output_dir / 'test.md')
    manifest_path = output_dir / 'test_manifest.json'
    assert manifest_path.exists()
    m = json.loads(manifest_path.read_text())
    assert m['source']['format'] == 'DOCX'
    print('OK')
"`

---

#### T1.3: Create Manifest Unit Tests
**File**: `tests/test_manifest_generation.py` (new)

**Tests to add**:
- test_manifest_generates_for_md_output
- test_manifest_generates_for_xlf_output
- test_manifest_captures_source_info
- test_manifest_captures_extraction_outputs
- test_manifest_captures_image_info
- test_manifest_captures_warnings

**Category**: `writing`
**Skills**: `writing`
**QA**: `pytest tests/test_manifest_generation.py -v`

---

### Phase 2: Skeleton Support

#### T2.1: Add skeleton Fields to ExtractionResult
**File**: `src/opp/utils/dataclasses.py`
**Lines**: 61-79

**Tasks**:
1. Add `Optional` import to typing if not present (line 2)
2. Add `skeleton` and `skeleton_files` fields to `ExtractionResult`:
   ```python
   skeleton: Optional[bytes] = None
   skeleton_files: Optional[List[str]] = None
   ```

**Category**: `quick`
**Skills**: `refactor`
**QA**: `python -c "from opp.utils.dataclasses import ExtractionResult; r=ExtractionResult([], [], []); print(hasattr(r, 'skeleton'), hasattr(r, 'skeleton_files'))"`

---

#### T2.2: Modify DOCXExtractor to Capture Skeleton
**File**: `src/opp/extractors/docx.py`
**Lines**: 24-51 (extract method)

**Tasks**:
1. Add `import zipfile` at top
2. Add `from typing import Optional` if not present
3. After line 38 (`images = self.extract_images(doc)`), add skeleton capture:
   ```python
   skeleton_bytes: Optional[bytes] = None
   skeleton_files: Optional[List[str]] = None
   try:
       with zipfile.ZipFile(input_path, 'r') as zf:
           skeleton_bytes = zf.read()
           key_files = [
               'word/document.xml',      # Main document content
               'word/styles.xml',         # Style definitions
               'word/numbering.xml',     # Numbering definitions
               'word/settings.xml',      # Document settings
               '[Content_Types].xml',   # Content type declarations
           ]
           skeleton_files = [f for f in key_files if f in zf.namelist()]
   except zipfile.BadZipFile:
       warnings.append("Skeleton extraction failed: not a valid ZIP/DOCX file")
       skeleton_bytes = None
       skeleton_files = None
   ```
4. Update `return ExtractionResult(...)` to include `skeleton=skeleton_bytes, skeleton_files=skeleton_files`

**Category**: `deep`
**Skills**: `refactor`
**QA**: `python -c "
from pathlib import Path
import tempfile, zipfile, io
from docx import Document
from opp.extractors.docx import DOCXExtractor

with tempfile.TemporaryDirectory() as tmpdir:
    docx_path = Path(tmpdir) / 'test.docx'
    doc = Document()
    doc.add_heading('Test')
    doc.save(str(docx_path))

    extractor = DOCXExtractor()
    result = extractor.extract(docx_path)
    assert result.skeleton is not None, 'skeleton is None'
    assert len(result.skeleton_files) > 0, 'skeleton_files empty'
    assert 'word/document.xml' in result.skeleton_files
    # Verify ZIP is valid
    with zipfile.ZipFile(io.BytesIO(result.skeleton), 'r') as zf:
        assert 'word/document.xml' in zf.namelist()
    print('OK')
"`

---

#### T2.3: Modify PPTXExtractor to Capture Skeleton
**File**: `src/opp/extractors/pptx.py`
**Lines**: 23-53 (extract method)

**Tasks**:
1. Add `import zipfile` at top
2. Add `from typing import Optional` if not present
3. After line 36 (`images = self.extract_images(prs)`), add skeleton capture:
   ```python
   skeleton_bytes: Optional[bytes] = None
   skeleton_files: Optional[List[str]] = None
   try:
       with zipfile.ZipFile(input_path, 'r') as zf:
           skeleton_bytes = zf.read()
           # PPTX key files: all files under ppt/ prefix
           skeleton_files = [f for f in zf.namelist() if f.startswith('ppt/')]
   except zipfile.BadZipFile:
       warnings.append("Skeleton extraction failed: not a valid ZIP/PPTX file")
       skeleton_bytes = None
       skeleton_files = None
   ```
4. Update `return ExtractionResult(...)` to include `skeleton=skeleton_bytes, skeleton_files=skeleton_files`

**Category**: `deep`
**Skills**: `refactor`
**QA**: `python -c "
from pathlib import Path
import tempfile, zipfile, io
from pptx import Presentation
from opp.extractors.pptx import PPTXExtractor

with tempfile.TemporaryDirectory() as tmpdir:
    pptx_path = Path(tmpdir) / 'test.pptx'
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(str(pptx_path))

    extractor = PPTXExtractor()
    result = extractor.extract(pptx_path)
    assert result.skeleton is not None, 'skeleton is None'
    assert any(f.startswith('ppt/') for f in result.skeleton_files), 'no ppt/ files'
    # Verify ZIP is valid
    with zipfile.ZipFile(io.BytesIO(result.skeleton), 'r') as zf:
        assert any(f.startswith('ppt/') for f in zf.namelist())
    print('OK')
"`

---

#### T2.4: Add save_skeleton() Method to OPPPipeline
**File**: `src/opp/pipeline.py`
**Lines**: 91-126 (after generate_xliff)

**Tasks**:
1. Add new method `save_skeleton()` to `OPPPipeline` class that:
   - Takes `result: ExtractionResult`, `base_name: str`, `output_dir: Path`
   - Returns `Optional[Path]`
   - Writes skeleton bytes to `{base_name}.skeleton.zip`

**Category**: `quick`
**Skills**: `refactor`
**QA**: `python -c "from opp.pipeline import OPPPipeline; from pathlib import Path; p=OPPPipeline(Path('./resources')); print(hasattr(p, 'save_skeleton'))"`

---

#### T2.5: Update cli.py to Call save_skeleton and Add to Manifest
**File**: `src/opp/cli.py`
**Lines**: ~200-214 (process_single_file function)

**Tasks**:
1. After manifest generation, add skeleton saving call to `pipeline.save_skeleton()`
2. Add skeleton info to manifest dict

**Category**: `quick`
**Skills**: `refactor`
**QA**: `ls -la /tmp/opp_test/*.skeleton.zip && unzip -l /tmp/opp_test/*.skeleton.zip | head -20`

---

#### T2.6: Create Skeleton Unit Tests
**File**: `tests/test_skeleton_preservation.py` (new)

**Tests to add**:
- test_docx_extractor_preserves_skeleton
- test_pptx_extractor_preserves_skeleton
- test_skeleton_zip_is_valid
- test_skeleton_contains_document_xml
- test_invalid_doc_no_skeleton
- test_pipeline_save_skeleton

**Category**: `writing`
**Skills**: `writing`
**QA**: `pytest tests/test_skeleton_preservation.py -v`

---

## 3. Atomic Commit Strategy

### Commit 1: Phase 1 - Manifest Infrastructure
- src/opp/cli.py (helper functions + manifest generation)
- tests/test_manifest_generation.py (new)

### Commit 2: Phase 2 Part A - Dataclass Changes
- src/opp/utils/dataclasses.py (new skeleton fields)
- src/opp/__init__.py (if needed for exports)

### Commit 3: Phase 2 Part B - Extractor Skeleton Capture
- src/opp/extractors/docx.py (zipfile skeleton capture)
- src/opp/extractors/pptx.py (zipfile skeleton capture)

### Commit 4: Phase 2 Part C - Pipeline and CLI Integration
- src/opp/pipeline.py (save_skeleton method)
- src/opp/cli.py (save_skeleton call + manifest update)

### Commit 5: Phase 2 - Tests
- tests/test_skeleton_preservation.py (new)

---

## 4. Wave-Based Parallel Execution

### Wave 1 (Sequential dependencies):
- **T2.1** (dataclass fields) must complete before **T2.2** (DOCX) and **T2.3** (PPTX)
- **T2.2** and **T2.3** can run in parallel (different files)

### Wave 2 (After Wave 1):
- **T2.4** (pipeline method) can run parallel to T2.2/T2.3 - only needs T2.1 (dataclass exists) and T2.2/T2.3 (extractors populate skeleton)
- **T1.3** (manifest tests) needs T1.2 to complete

### Wave 3 (Integration):
- **T2.5** (CLI integration) needs T2.4 to complete
- **T2.6** (skeleton tests) needs T2.2, T2.3, T2.4 to complete

### Wave 4 (Final):
- Full test suite: `pytest tests/ -q`
- Integration verification

---

## 5. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Large skeleton files (50MB+)** | Disk space, memory | Document skeleton behavior; for large files, downstream tools can skip skeleton processing. `--no-skeleton` CLI flag is a future extension (see Section 9). |
| **Sensitive metadata in docProps** | Info leakage | Document that docProps/core.xml may contain author/company info; add optional stripping (future extension) |
| **Invalid ZIP structure** | Skeleton corruption | `try/except zipfile.BadZipFile` with warning, no blocking |
| **Memory pressure** | OOM on large files | `zf.read()` loads full ZIP decompressed. For large files, use `--no-skeleton` flag. Skeleton save uses chunked write via `shutil.copyfileobj()` |
| **Existing tests break** | Regression | Run full test suite after each commit |
| **Backwards compatibility** | API breakage | `Optional[bytes] = None` default ensures no breaking changes |

---

## 6. QA Verification Steps

### Per-Task QA:
| Task | Verification Command |
|------|---------------------|
| T1.1 | `python -c "from opp.cli import _detect_format_from_extension; from pathlib import Path; print(_detect_format_from_extension(Path('test.docx')))"` |
| T1.2 | Inline Python script (see T1.2 QA section above) |
| T1.3 | `pytest tests/test_manifest_generation.py -v` |
| T2.1 | `python -c "from opp.utils.dataclasses import ExtractionResult; r=ExtractionResult([], [], []); print(hasattr(r, 'skeleton'), hasattr(r, 'skeleton_files'))"` |
| T2.2 | Inline Python script (see T2.2 QA section above) |
| T2.3 | Inline Python script (see T2.3 QA section above) |
| T2.4 | `python -c "from opp.pipeline import OPPPipeline; from pathlib import Path; p=OPPPipeline(Path('./resources')); print(hasattr(p, 'save_skeleton'))"` |
| T2.5 | Inline Python script (E2E verification script below calls save_skeleton) |
| T2.6 | `pytest tests/test_skeleton_preservation.py -v` |

### Final Verification:
```bash
# Full test suite
pytest tests/ -q --tb=short

# Manual E2E verification (creates real DOCX in tmpdir)
python -c "
from pathlib import Path
import tempfile, json, zipfile, io
from docx import Document
from opp.pipeline import OPPPipeline

with tempfile.TemporaryDirectory() as tmpdir:
    # Create test DOCX
    docx_path = Path(tmpdir) / 'test.docx'
    doc = Document()
    doc.add_heading('Test Heading')
    doc.add_paragraph('Some paragraph text.')
    doc.save(str(docx_path))

    # Run OPP pipeline
    output_dir = Path(tmpdir) / 'output'
    output_dir.mkdir()
    resources_dir = Path(tmpdir) / 'resources'
    pipeline = OPPPipeline(resources_dir)
    result = pipeline.process_file(docx_path)
    pipeline.generate_markdown(result.extraction_result, output_dir / 'test.md')
    pipeline.generate_xliff(result.extraction_result, output_dir / 'test.xlf', 'en', 'zh')

    # Verify outputs
    assert (output_dir / 'test.md').exists(), 'test.md missing'
    assert (output_dir / 'test.xlf').exists(), 'test.xlf missing'
    assert (output_dir / 'test_manifest.json').exists(), 'test_manifest.json missing'

    # Verify manifest structure
    m = json.loads((output_dir / 'test_manifest.json').read_text())
    assert m['source']['format'] == 'DOCX', f\"Got format {m['source']['format']}\"
    assert m['extraction']['outputs']['markdown']['path'] == 'test.md'
    assert m['extraction']['outputs']['xliff']['path'] == 'test.xlf'

    # Verify skeleton.zip (Phase 2 feature)
    skeleton_path = pipeline.save_skeleton(result.extraction_result, 'test', output_dir)
    assert skeleton_path is not None, 'save_skeleton returned None'
    assert skeleton_path.exists(), f'skeleton.zip not created at {skeleton_path}'
    with zipfile.ZipFile(skeleton_path, 'r') as zf:
        names = zf.namelist()
        assert 'word/document.xml' in names, 'word/document.xml not in skeleton'
    assert result.extraction_result.skeleton_files is not None
    assert len(result.extraction_result.skeleton_files) > 0

    print('All E2E checks passed')
"
```

---

## 7. Test Commands Summary

```bash
# Unit tests for new features
pytest tests/test_manifest_generation.py -v
pytest tests/test_skeleton_preservation.py -v

# Existing test suite (ensure no regression)
pytest tests/ -q --tb=short

# Specific extractor tests
pytest tests/test_docx_extractor.py tests/test_pptx_extractor.py -v

# E2E tests
pytest tests/test_docx_e2e.py tests/test_pptx_e2e.py -v
```

---

## 8. File Summary

| File | Action | Lines |
|------|--------|-------|
| `src/opp/cli.py` | Add helpers + manifest generation + skeleton save | ~1-17, ~162-230 |
| `src/opp/utils/dataclasses.py` | Add skeleton fields | ~61-79 |
| `src/opp/extractors/docx.py` | Add zipfile skeleton capture | ~24-51 |
| `src/opp/extractors/pptx.py` | Add zipfile skeleton capture | ~23-53 |
| `src/opp/pipeline.py` | Add save_skeleton method | ~128-145 |
| `tests/test_manifest_generation.py` | New test file | N/A |
| `tests/test_skeleton_preservation.py` | New test file | N/A |

---

## 9. Implementation Notes

### Memory Efficiency
- For skeleton capture: Use `zf.read()` which loads full ZIP decompressed content into memory
- For large files (>50MB): Consider streaming with `zf.open()` + `shutil.copyfileobj()`
- Default chunk size for MD5: 8192 bytes (already in helper function)

### Security Considerations
- MD5 is acceptable here for file deduplication/integrity checking within controlled environment
- For production with adversarial inputs, recommend SHA-256 (but adds overhead)
- docProps/core.xml may contain author, lastModifiedBy, created date - not stripped by default

### Backwards Compatibility
- `ExtractionResult` dataclass: new fields use `Optional[bytes] = None` default - fully backwards compatible
- `OPPPipeline.save_skeleton()`: returns `Optional[Path]` - `None` if no skeleton, no breaking change
- CLI: manifest.json is additive - existing output unchanged

### Future Extensions (Not in Scope)
1. `--skeleton-mode full|minimal|none` CLI option
2. Skeleton compression (`zipfile.ZIP_DEFLATED`)
3. Metadata stripping from docProps/core.xml
4. Batch manifest aggregation
