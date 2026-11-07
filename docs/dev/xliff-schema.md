# OPP XLIFF output schema + PDF/XLIFF limitation (moved from AGENTS.md, OPP#119)

## XLIFF output schema

`src/opp/xliff/generator.py` produces XLIFF 1.2 or 2.0. Each
`<trans-unit>` carries the source text + inline tags (`<bx>` / `<ex>` /
`<it>`) for format preservation. ORF's `apply-xliff` reverses the
process.

`Pipeline.is_complete()` (in OL's `src/ol_md/pipeline.py` — OL side,
not OPP) validates the XLIFF is fully translated.

## PDF / XLIFF limitation

**PDF → XLIFF is intentionally blocked.** OPP can extract PDF → MD
(via pypdf + pdfplumber), but `generate_xliff` raises on PDF input
because PDF structure is too lossy for clean XLIFF `<trans-unit>`
extraction. Use the MD path with a downstream translation step
that produces a new XLIFF, or translate the MD directly.