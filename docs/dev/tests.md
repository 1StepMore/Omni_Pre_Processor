# OPP tests (moved from AGENTS.md, OPP#119)

```bash
make test                            # all tests via uv run pytest tests/ -v
pytest tests/test_html_extractor.py  # HTML extractor only
pytest tests/test_e2e_75_html_image_dedup.py  # specific E2E regression
```

Coverage target ≥90% (per `pyproject.toml [tool.coverage]`).

Key test files:
- `tests/test_html_extractor.py` — HTML extractor (readability/docling)
- `tests/test_md_generator.py` — MD output format
- `tests/test_xliff_generator.py` — XLIFF 1.2/2.0
- `tests/test_e2e_75_html_image_dedup.py` — image dedup regression
- `tests/test_e2e_81_csv_multiline.py` — multi-line CSV cells
- `tests/test_e2e_82_docling_fallback.py` — docling fallback
- `tests/test_resource_manager.py` — image MD5+UUID naming
- `tests/test_pipeline_pdf2html_integration.py` — pipeline integration (PDF → HTML channel)
- `tests/test_pipeline_pdf_xliff_guard.py` — pipeline integration guard (PDF → XLIFF refusal)