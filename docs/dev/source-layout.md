# OPP source layout (moved from AGENTS.md, OPP#119)

Full annotated tree of `src/opp/`:

```
src/opp/
├── cli.py                # `opp` CLI entry
├── pipeline.py           # OPPPipeline orchestrator
├── detector.py           # Magic-bytes format detection
├── extractors/           # One extractor per input format
│   ├── docx.py           # python-docx-based DOCX extraction
│   ├── pptx.py           # python-pptx-based PPTX extraction
│   ├── pdf.py            # PDF (pypdf + pdfplumber)
│   ├── xlsx.py           # openpyxl
│   ├── csv.py            # pandas (E2E-81: now warns on bad lines)
│   ├── json.py, xml.py   # Pure Python
│   ├── html.py           # readability + docling (E2E-82: falls back)
│   ├── epub.py           # ebooklib
│   ├── email.py          # email stdlib (EML/MSG)
│   ├── image_ocr.py      # Tesseract / RapidOCR
│   ├── youtube.py        # markitdown[youtube-transcription]
│   └── …
├── channels/            # Output formatters (MD / XLIFF)
│   ├── md_bus.py         # MD output bus
│   ├── table_channel.py  # DataFrame → MD table
│   ├── xliff/            # XLIFF 1.2 / 2.0 generators
│   └── markdown/         # MDGenerator (E2E-75: is_inline_in_md)
├── mcp/                  # MCP server (the Agent-facing surface)
│   ├── server.py         # Standard mcp library, 9 tools
│   ├── config.py         # MCPConfig dataclass (E2E-76: reads OPP_MCP_*)
│   ├── security.py       # PathValidator
│   ├── auth.py           # MCP_SHARED_SECRET auth
│   └── rate_limiter.py   # Per-MCP-tool token bucket
├── resource_manager.py   # Image dedup (MD5 + UUID naming)
├── parsers/              # frontmatter + XLIFF parsers
└── config/               # YAML config + loaders
```