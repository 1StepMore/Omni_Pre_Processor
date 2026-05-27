# OPP Batch Test Directory

This directory contains sample files for testing all supported OPP formats and edge cases.

## Directory Structure

```
batch_test/
├── phase0_office/          # Office documents (DOCX, PPTX, PDF)
├── phase5_data/            # Data formats (XLSX, CSV, JSON, XML)
├── phase6_web/             # Web formats (HTML, EPUB)
├── phase7_email_image/      # Email and images (EML, PNG)
├── phase8_media/           # Rich media (IPYNB, YouTube URL)
└── edge_cases/            # Error/edge case files
```

## File Inventory

### Phase 0: Office Documents
| File | Description |
|------|-------------|
| `normal.docx` | Standard DOCX with headings, paragraphs, table |
| `empty.docx` | Empty DOCX document |
| `single_paragraph.docx` | Single paragraph DOCX |
| `with_lists.docx` | DOCX with ordered and unordered lists |
| `normal.pptx` | Standard PPTX with 2 slides, notes |
| `empty.pptx` | Empty PPTX |
| `normal.pdf` | Single page PDF |
| `multipage.pdf` | 3-page PDF |

### Phase 5: Data Formats
| File | Description |
|------|-------------|
| `normal.xlsx` | Multi-sheet XLSX with headers |
| `empty.xlsx` | Empty XLSX workbook |
| `single_row.xlsx` | XLSX with only header row |
| `normal.csv` | CSV with headers and data |
| `no_header.csv` | CSV without header row |
| `special_chars.csv` | CSV with commas, quotes, newlines |
| `empty.csv` | Empty CSV file |
| `normal.json` | Nested JSON object |
| `flat.json` | Flat JSON key-value pairs |
| `with_arrays.json` | JSON with arrays and booleans |
| `normal.xml` | XML with namespace |
| `simple.xml` | Simple XML structure |

### Phase 6: Web and Ebooks
| File | Description |
|------|-------------|
| `normal.html` | HTML with nav, article, code blocks, table |
| `simple.html` | Simple HTML with one paragraph |
| `with_code.html` | HTML with Python code block |
| `normal.epub` | EPUB with chapter |
| `simple.epub` | Simple single-chapter EPUB |

### Phase 7: Email and Images
| File | Description |
|------|-------------|
| `plain.eml` | Plain text email |
| `html.eml` | HTML email with plain fallback |
| `normal.png` | 100x100 RGB PNG |
| `large.png` | 500x500 RGB PNG |
| `simple.png` | 10x10 RGB PNG |

### Phase 8: Rich Media
| File | Description |
|------|-------------|
| `normal.ipynb` | Notebook with markdown and code |
| `markdown_only.ipynb` | Markdown-only notebook |
| `code_only.ipynb` | Code-only notebook |
| `normal.url` | YouTube watch URL |
| `short.url` | YouTube short URL |
| `embed.url` | YouTube embed URL |

### Edge Cases
| File | Description |
|------|-------------|
| `corrupted.docx` | Invalid DOCX (not a zip) |
| `corrupted.pdf` | Invalid PDF content |
| `corrupted.json` | Malformed JSON |
| `corrupted.xml` | Unclosed tags |
| `zero_byte.*` | Zero-byte files |
| `wrong_ext.pdf` | PDF content with wrong extension |
| `file with spaces.docx` | Filename with spaces |
| `文档测试.docx` | Unicode filename |

## Usage

### Test with OPP CLI

```bash
# Test all files in a phase directory
opp --target-format=both --source-lang=en --target-lang=zh --output-dir=output phase0_office/

# Test single file
opp document.docx --target-format=md

# Batch process entire test directory
opp --batch --output-dir=output batch_test/

# Detect format without processing
opp --detect-format batch_test/**/*.docx
```

### Test Specific Format

```bash
# Test all DOCX files
opp --target-format=md --output-dir=md_output batch_test/phase0_office/*.docx

# Test all JSON files
opp --target-format=xlf --source-lang=en --target-lang=zh batch_test/phase5_data/*.json
```

### Expected Results

| Format | MD Output | XLIFF Output |
|--------|-----------|--------------|
| DOCX | Full markdown | Trans-units per paragraph |
| PPTX | Slide text + notes | Trans-units per slide |
| PDF | Extracted text | (PDF not supported for XLIFF) |
| XLSX | Table markdown | One trans-unit per row |
| CSV | Table markdown | One trans-unit per row |
| JSON | Flat text | Key-value trans-units |
| XML | Element text | Element trans-units |
| HTML | Clean article | Trans-units per paragraph |
| EPUB | Chapter text | Chapter trans-units |
| EML | Headers + body | Header + body trans-units |
| IPYNB | Markdown cells | Cell trans-units |

## Notes

- Files marked "empty" may produce warnings or empty output
- Corrupted files should trigger error handling but not crash OPP
- Zero-byte files should be detected and skipped with warning
- Unicode filenames work on UTF-8 systems
