# Phase 5 Learnings

## Context Gathering Findings (2026-05-10)

### ExtractorBase Interface
- **Class name**: `ExtractorBase` (NOT `BaseExtractor`)
- **Location**: `src/opp/extractors/base.py`
- **Required methods**:
  - `supported_extensions() -> List[str]`
  - `extract(input_path: Path) -> ExtractionResult`
- **Return type**: `ExtractionResult` (dataclass with paragraphs, tables, images, metadata, warnings)
- **Registration**: Hardcoded dict in `OPPPipeline.__init__`

### Pipeline Registration Pattern
```python
self.extractors: Dict[FormatType, ExtractorBase] = {
    FormatType.DOCX: DOCXExtractor(),
    FormatType.PPTX: PPTXExtractor(),
    FormatType.PDF: PDFExtractor(),
}
```

### FormatType Enum (current)
```python
class FormatType(Enum):
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    UNKNOWN = "unknown"
```
Missing: XLSX, CSV, JSON, XML

### Detector Detection Logic
- Magic bytes: ZIP (PK) for DOCX/PPTX, PDF (%PDF) for PDF
- Extension-based fallback with 0.5 confidence for known formats
- XLSX would use same PK magic as DOCX/PPTX, then check .xlsx extension

### Dependencies (pyproject.toml)
- Core: python-docx, python-pptx, pymupdf, translate-toolkit, lxml
- office optional: openpyxl>=3.0.0, pandas>=2.0.0
- **chardet is NOT present** - need to add it

### XLIFF Structure
- Version: 1.2 (via translate-toolkit library)
- Unit element: `trans-unit` (standard XLIFF 1.2)
- Uses `translate.storage.xliff.xlifffile` class

### openpyxl data_only Behavior
- `data_only=True`: Returns cached values (from last Excel save) or **None** for uncalculated formulas
- `data_only=False`: Returns formula strings
- For formula cells without cached values → returns **None** (not formula string!)
- Multi-sheet: `wb.sheetnames` lists all sheets, `wb["SheetName"]` accesses

### Key Files to Modify
1. `src/opp/detector.py` - Add XLSX, CSV, JSON, XML to FormatType + detection logic
2. `src/opp/pipeline.py` - Register new extractors in self.extractors dict
3. `pyproject.toml` - Add chardet dependency
4. `src/opp/extractors/__init__.py` - Export new extractors