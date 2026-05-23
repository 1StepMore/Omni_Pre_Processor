# PDF Extractor Fix - Learning Log

## Session Info
- Plan: pdf-extractor-fix
- Session: ses_1d67f2865ffeSg5rXkvp218D98
- Started: 2026-05-15T03:42:41Z

## Key Decisions Made

### Chinese Heading Patterns
- `"^[一二三四五六七八九十百千零两]+、` → level 1 (一，二，三、)
- `"^第[一二三四五六七八九十百千万零两\\d]+章"` → level 1 (第一章，第1章)
- `"^第[一二三四五六七八九十百千万零两\\d]+节"` → level 2 (第一节)
- `"^\\d+\\."` → level 1 (1. 2. 3.)
- `"^\\d+\\.\\d+"` → level 2 (1.1 2.1)

### Table Fix
- Change `rows = extracted` to `rows = extracted[1:]`
- Edge case: if `len(extracted) <= 1`, skip table (no data rows)

### TOC Integration
- Call `extract_toc()` inside `extract()` after getting doc
- Prepend TOC entries to paragraph list
- Dedupe by `(text.strip(), level)` tuple

## Issues Found During Analysis

1. **Double-open bug**: `extract_toc()` opens file itself, so calling from `extract()` would double-open
   - Fix: Refactor `extract_toc()` to accept already-open doc OR pass doc reference

2. **Fallback header detection**: If `table.header.names` is empty but `extracted[0]` has content, use `extracted[0]` as header

## Code Changes

### File: src/opp/extractors/pdf.py
1. Line 151: `rows = extracted` → `rows = extracted[1:]`
2. Add `_detect_heading_level()` method
3. Modify `extract()` to call TOC and merge