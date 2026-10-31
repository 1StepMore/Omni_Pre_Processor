---
name: opp-dev
description: Develop inside the OPP sub-repo — add a new input-format extractor, extend the MCP tool surface, wire skeleton production, or touch the extraction pipeline. Use when asked to 加输入格式/提取器、改 OPP MCP 工具、动 skeleton 生产、或修 OPP 的提取行为。
---

# OPP dev — adding extractors, formats, and MCP surface

Checklist-driven SOP. `scripts/coverage_matrix.py --check` and
`scripts/doc_inventory.py --check` enforce the numbers/paths — run both
before pushing.

## Adding a new input format (a new extractor)

1. **Extractor**: `src/opp/extractors/<fmt>.py` — subclass
   `ExtractorBase` (see the existing 16 in
   `src/opp/extractors/__init__.py::__all__`); return
   `ExtractionResult` (MD content + optional skeleton artifacts).
2. **Registration**: add the class to `__all__` AND to
   `_INPUT_FORMATS` in `src/opp/mcp/tools/get_capabilities.py` —
   the doc gate derives "16 input formats" from that list and the
   coverage matrix derives its row set from the same source.
3. **Optional dependency**: if the format needs an optional package or
   external binary (the `msg` / `ipynb` / OCR pattern — ImportError →
   graceful degradation, never a crash), guard the import and update the
   ⚠️ row in `docs/dev/production-matrix.md`.
4. **Skeleton** (if the format should join the XLIFF channel): emit
   `<stem>.skeleton.zip` from the pipeline (the XLSX `xliff_map.json` /
   EML `eml_map.json` sidecar pattern is the contract for formats whose
   container cannot carry injected attributes).
5. **Scenarios**: add `opp-*` scenarios under `scenarios/` (tier 1 =
   hermetic; real-extraction tiers declare their deps) and keep the
   suite coverage audit green.
6. **Gates**: `python scripts/coverage_matrix.py --check` +
   `python scripts/doc_inventory.py --check` (regenerate if stale).

## Extending the MCP tool surface

1. Tool function under `src/opp/mcp/tools/` + schema entry in
   `src/opp/mcp/server.py::_TOOL_SCHEMAS` (the "9 tools" claim derives
   from this list).
2. Error envelope: raise `McpError` (see `src/opp/mcp/_errors.py`) —
   never return bare exceptions; the error codes are documented in
   `docs/API.md`.
3. Path arguments go through `get_path_validator()` — fail-CLOSED; an
   unset allowlist refuses service (see `docs/API.md` security section).
4. Scenarios: `tool-opp-<name>` in the suite repo (agent-surface
   family) or in-repo `scenarios/` for OPP-specific behaviors.
5. Gates as above.

## Gates to run before pushing

```bash
make test                                       # full unit suite
ruff check --select F src/                      # OPP's own lint gate
python scripts/coverage_matrix.py --check       # production matrix truth
python scripts/doc_inventory.py --check         # doc truth
```
