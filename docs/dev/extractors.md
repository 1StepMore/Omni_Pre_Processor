# OPP extractor architecture (moved from AGENTS.md, OPP#119)

Each format has a dedicated extractor under `src/opp/extractors/`.
All extractors share the same base class `ExtractorBase`
(`src/opp/extractors/base.py`) which defines:

```python
class ExtractorBase:
    def supported_extensions(self) -> list[str]: ...
    def extract(self, input_path: Path) -> ExtractionResult: ...
    def validate_file(self, input_path: Path) -> None: ...
    def get_file_info(self, input_path: Path) -> DocumentMetadata: ...
```

`ExtractionResult` (in `src/opp/utils/dataclasses.py`) carries:
- `paragraphs: list[ParagraphData]`
- `tables: list[TableData]`
- `images: list[ImageData]` (with `is_floating`, `wp_anchor_h/v`, `is_inline_in_md` since v0.6.0/0.6.4)
- `metadata: DocumentMetadata`
- `warnings: list[str]`
- `skeleton: bytes | None` (the skeleton.zip for ORF)

**Direct-use extractor note**: `PDFExtractor` (`src/opp/extractors/pdf.py`)
is a supported direct-use API (TOC via `extract_toc`, OCR fallback) but is
not in the pipeline registry: `OPPPipeline` routes `.pdf` to
`PDF2HTMLExtractor` for image-preserving HTML output. Callers that need
TOC/OCR instantiate `PDFExtractor` explicitly.

**To add a new extractor**:

1. Create `src/opp/extractors/<format>.py` with a class
   extending `ExtractorBase`
2. Implement `supported_extensions()` and `extract()`
3. Register it in `src/opp/extractors/__init__.py`
4. Add tests in `tests/test_<format>_extractor.py`
5. Add the format to `src/opp/detector.py` magic-bytes table
6. If it produces images, emit `ImageData(is_inline_in_md=...)` correctly
   so `MarkdownGenerator` dedup works (E2E-75)