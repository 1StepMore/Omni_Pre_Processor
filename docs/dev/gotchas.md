# OPP known issues / gotchas (moved from AGENTS.md, OPP#119)

- **E2E-15**: `MarkdownGenerator` filters out orphan images. If an
  image has no paragraph anchor, it goes to the trailing `## Images`
  block instead of being inlined.
- **E2E-75**: HTML input → every image is `is_inline_in_md=True`
  (markdownify already embedded the ref). `MarkdownGenerator`
  dedup checks this flag and skips the generator's own inline
  injection + the trailing `## Images` block.
- **E2E-81**: CSV input with quoted multi-line cells now passes
  through cleanly. `pd.read_csv(on_bad_lines="warn")` surfaces
  mis-parses; `_escape_table_cell` escapes `\n` as `<br>` for
  pandoc tables.
- **E2E-82**: `HTMLExtractor` now falls back to readability when
  docling raises or returns empty. Previously a docling OOM/timeout
  produced a 0-character `.md` with no error.
- **`opp -v`** writes to stderr (since v0.6.2) — so MCP logging
  doesn't capture it.
- **PDF→XLIFF** is blocked by design (see [PDF / XLIFF limitation](xliff-schema.md#pdf--xliff-limitation)).
- **`.url` (YouTube)**: auto-detected and routed to
  `markitdown[youtube-transcription]`. Requires the `[youtube]`
  extra.