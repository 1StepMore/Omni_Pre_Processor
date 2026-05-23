# Phase 5: Office与数据格式扩展 (XLSX/CSV/JSON/XML)

## TL;DR

> **Quick Summary**: Extend OPP to support XLSX/CSV/JSON/XML extraction, mapping tabular data to Markdown tables and nested structures to XLIFF translation units with context preserved.
>
> **Deliverables**:
> - XLSXExtractor with multi-sheet support (data_only=True mode)
> - CSVExtractor with pandas dialect inference (sep=None)
> - JSONExtractor with dot-notation key paths
> - XMLExtractor with namespace auto-strip or mapping table
> - TableChannel for MD table generation
> - KeyValueChannel for XLIFF trans-unit generation
>
> **Estimated Effort**: 1.5 days
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 4 → Task 6 → Task 9 → Task 12

---

## Context

### Original Request
Phase 5 of OPP development plan (v4.0-Phase-Full) - Office与数据格式扩展 (XLSX/CSV/JSON/XML)

### Document Defaults Applied (from OPP增补完整版.md)

| Decision | Default Applied | Source |
|----------|-----------------|--------|
| XLSX formula取值 | `openpyxl data_only=True` mode | Phase 5 风险缓解 |
| CSV dialect | pandas `pd.read_csv(sep=None)` auto-inference | Phase 5 风险缓解 |
| JSON key format | Dot-notation (`outer.inner`) | BDD场景2 |
| XML namespace | Auto-strip or preserve mapping table | Phase 5 风险缓解 |
| Row limit | 10,000 rows max (paginate beyond) | 边界条件验收标准 |
| Nested depth | JSON/XML >8 layers auto-truncate + warning | 边界条件验收标准 |
| Memory strategy | Streaming CSV, memory not linear with file size | 边界条件验收标准 |
| Performance | ≥10MB/s for XLSX/CSV | 非功能性验收标准 |
| Dependencies | Only pandas, openpyxl, lxml, chardet | 非功能性验收标准 |

---

## Work Objectives

### Core Objective
Add XLSX/CSV/JSON/XML extraction support to OPP, enabling tabular data → MD tables and key-value data → XLIFF translation units with full context preservation.

### Concrete Deliverables

| # | File | Description |
|---|------|-------------|
| 1 | `src/opp/extractors/xlsx.py` | XLSXExtractor (multi-sheet, data_only=True) |
| 2 | `src/opp/extractors/csv.py` | CSVExtractor (pandas inference) |
| 3 | `src/opp/extractors/json.py` | JSONExtractor (dot-notation keys) |
| 4 | `src/opp/extractors/xml.py` | XMLExtractor (namespace handling) |
| 5 | `src/opp/channels/table_channel.py` | TableChannel (DataFrame → MD) |
| 6 | `src/opp/channels/keyvalue_channel.py` | KeyValueChannel (dict → XLIFF) |
| 7 | `src/opp/extractors/__init__.py` | Update exports |
| 8 | `src/opp/channels/__init__.py` | Channel exports |
| 9 | `src/opp/pipeline.py` | Route new formats |
| 10 | `tests/test_xlsx_extractor.py` | 20+ test cases |
| 11 | `tests/test_csv_extractor.py` | 20+ test cases |
| 12 | `tests/test_json_extractor.py` | 20+ test cases |
| 13 | `tests/test_xml_extractor.py` | 20+ test cases |
| 14 | `tests/test_table_channel.py` | Channel tests |
| 15 | `tests/test_keyvalue_channel.py` | Channel tests |

### Definition of Done

- [ ] `pytest tests/test_xlsx_extractor.py tests/test_csv_extractor.py tests/test_json_extractor.py tests/test_xml_extractor.py -v` → ALL PASS
- [ ] `pytest tests/test_table_channel.py tests/test_keyvalue_channel.py -v` → ALL PASS
- [ ] All extractors implement `ExtractorInterface` (extends base.py)
- [ ] `python -c "from opp import XLSXExtractor, CSVExtractor, JSONExtractor, XMLExtractor"` → NO ERROR
- [ ] Pipeline auto-detects XLSX/CSV/JSON/XML via magic bytes
- [ ] New dependencies install: `pip install opp[data]` or explicit `pandas openpyxl lxml`

### Must Have

- XLSX: multi-sheet extraction, cell value reading (data_only=True), merged cell anchor-only
- CSV: encoding auto-detection (chardet), dialect inference (sep=None), header row config
- JSON: dot-notation key paths (`config.dashboard.menu.save`), null/empty skip
- XML: namespace stripping or mapping preservation, mixed content text concat
- Channels: DataFrame → MD table, dict → XLIFF trans-unit with context

### Must NOT Have

- Formula evaluation (only cached values via data_only=True)
- External API calls
- Image/OLE extraction from XLSX
- Password-protected file support
- .xls (old binary) support
- Breaking changes to Phase 0-4 APIs

---

## Verification Strategy

### Test Decision

- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD)
- **Framework**: pytest
- **TDD Flow**: 🔴 RED (write tests first) → 🟢 GREEN (implement) → 🔄 REFACTOR

### QA Policy

Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

- **Extractors**: Unit tests via pytest
- **Channels**: Unit tests via pytest
- **Integration**: E2E smoke test with sample files

---

## Execution Strategy

### Parallel Waves

```
Wave 0 (Infrastructure - BLOCKING ALL - execute first):
├── Task 0: Create channels dir, fixtures, add chardet dep, extend FormatType

Wave 1 (Extractors - 4 parallel, after Wave 0):
├── Task 1: XLSXExtractor [data_only, multi-sheet, merged cells]
├── Task 2: CSVExtractor [pandas inference, encoding detection]
├── Task 3: JSONExtractor [dot-notation, nested flatten]
├── Task 4: XMLExtractor [namespace strip, mixed content]

Wave 2 (Channels + Integration - 5 tasks):
├── Task 5: TableChannel (DataFrame → MD table)
├── Task 6: KeyValueChannel (dict → XLIFF)
├── Task 7: Pipeline update (format routing)
├── Task 8: Export updates (__init__.py)
├── Task 9: XLSXExtractor tests (TDD RED)

Wave 3 (Tests - 6 tasks):
├── Task 10: CSVExtractor tests (TDD RED)
├── Task 11: JSONExtractor tests (TDD RED)
├── Task 12: XMLExtractor tests (TDD RED)
├── Task 13: TableChannel tests
├── Task 14: KeyValueChannel tests
├── Task 15: E2E smoke test

Wave FINAL (Verification):
├── Task F1: Plan compliance audit
├── Task F2: Code quality review
├── Task F3: Coverage verification
└── Task F4: Integration verification

---

## TODOs

- [x] 0. Infrastructure setup (BLOCKING ALL OTHER TASKS)
- [x] 1. XLSXExtractor implementation
- [x] 2. CSVExtractor implementation
- [x] 3. JSONExtractor implementation
- [x] 4. XMLExtractor implementation
- [x] 5. TableChannel implementation
- [x] 6. KeyValueChannel implementation
- [x] 7. Pipeline update for new formats
- [x] 8. Export updates
- [x] 9. XLSXExtractor tests
- [x] 10. CSVExtractor tests
- [x] 11. JSONExtractor tests
- [x] 12. XMLExtractor tests
- [x] 13. TableChannel tests
- [x] 14. KeyValueChannel tests
- [x] 15. E2E smoke test

## Final Verification Wave

- [x] F1. **Plan compliance audit** — `oracle` - APPROVE
- [x] F2. **Code quality review** — `unspecified-high` - APPROVE
- [x] F3. **Coverage verification** — `unspecified-high` - APPROVE
- [x] F4. **Integration verification** — `unspecified-high` - APPROVE
  Test full pipeline: `opp convert file.xlsx --target-format both`

---

## Success Criteria

### Verification Commands

```bash
# All extractor tests pass
pytest tests/test_xlsx_extractor.py tests/test_csv_extractor.py tests/test_json_extractor.py tests/test_xml_extractor.py -v

# All channel tests pass
pytest tests/test_table_channel.py tests/test_keyvalue_channel.py -v

# E2E smoke test
pytest tests/test_phase5_e2e.py -v

# Import verification
python -c "from opp import XLSXExtractor, CSVExtractor, JSONExtractor, XMLExtractor"
python -c "from opp.channels import TableChannel, KeyValueChannel"

# Coverage check
pytest tests/test_xlsx_extractor.py tests/test_csv_extractor.py tests/test_json_extractor.py tests/test_xml_extractor.py --cov=src/opp/extractors --cov-report=term-missing
```

### Final Checklist

- [ ] All 4 extractors implemented and passing tests
- [ ] Both channels implemented and passing tests
- [ ] Pipeline updated with format routing
- [ ] No breaking changes to Phase 0-4
- [ ] Coverage ≥80% on new code
- [ ] All imports work correctly