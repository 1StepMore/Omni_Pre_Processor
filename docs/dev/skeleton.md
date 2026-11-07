# OPP skeleton preservation (moved from AGENTS.md, OPP#119)

For DOCX/PPTX/EPUB/HTML/XLSX, OPP also produces a `skeleton.zip` alongside
the XLIFF. It contains the original ZIP structure (DOCX = `word/`,
`[Content_Types].xml`; PPTX = `ppt/slides/`, `ppt/media/`; EPUB =
`OEBPS/`, `META-INF/`). ORF's `apply-xliff` reads the skeleton to
re-inject translated text without re-rendering styles or losing
media.

The two non-OOXML formats do not preserve an archive, so they synthesise
the skeleton instead, and ORF reads each shape its own way:

- **HTML** — a ZIP holding a single `index.html` whose blocks carry
  `data-trans-unit-id` attributes (see `HTML_SKELETON_ENTRY_NAME`).
- **XLSX** — the original workbook bytes verbatim plus an
  `xliff_map.json` sidecar. The map is a sidecar rather than injected
  attributes because SpreadsheetML is strict OOXML and rejects them.

EML, MSG and the data formats (CSV/JSON/XML) produce no skeleton: there is
no layout to preserve. For EML that is a recorded decision rather than an
omission — see the suite's `ACCEPTED_GAPS.md`.