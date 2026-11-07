# OPP image pipeline (moved from AGENTS.md, OPP#119)

OPP emits image references into the MD output via two paths:

1. **Inline images** (`ImageData.element_index` set) — written into
   the MD paragraph by `MarkdownGenerator._escape_inline`.
2. **DOCX drawings** (`ImageData.paragraph_index` or
   `is_floating=True`) — preserved in skeleton.zip; ORF reinjects
   during `apply-xliff`.

For HTML inputs, `is_inline_in_md=True` is set for every image
because `_html_to_markdown` (via `markdownify`) already embeds
`![…](src)` refs. Without this flag, `MarkdownGenerator` would
double-embed the same image (E2E-75).

For DOCX floating drawings, `ImageData.is_floating=True` and
`wp_anchor_h` / `wp_anchor_v` (in EMU) carry the position so ORF
can rebuild `<wp:anchor>` blocks.