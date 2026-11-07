# OPP CLI reference (moved from AGENTS.md, OPP#119)

| Command | Purpose |
|---------|---------|
| `opp <file> --target-format md|xliff|both --output-dir <dir>` | Extract a single document |
| `opp <file> --source-lang en --target-lang zh` | Specify language pair (otherwise uses config defaults) |
| `opp <file> --no-embed-images` | Don't base64-inline images into the MD (E2E-05 style) |
| `opp <file> --style-map '{"a5":1}'` | Promote paragraph style `a5` to H1 (pandoc) |
| `opp --detect-format <file>` | Format detection only |
| `opp -v <file> …` | Verbose (writes to **stderr** since v0.6.2) |
| `opp mcp` | Start the MCP server (stdio) |
| `opp --batch <file1> <file2> …` | Batch extract |