# OPP Inline Formatting Tracking - Implementation Plan

**Version**: v1.2  
**Author**: Sisyphus  
**Date**: 2026-05-22  
**Project**: Omni-Pre-Processor (OPP)  
**Goal**: Track inline formatting (bold, italic, underline) during extraction and encode as XLIFF inline elements for downstream preservation

---

## ⚠️ CRITICAL BUG FOUND - MUST FIX BEFORE CONTINUING

### Bug: `_escape_xml()` Breaks Inline Elements

**Location**: `src/opp/xliff/generator.py` lines 54-61 and 116-137

**Problem**: 
1. `encode_inline_elements()` produces source text like: `Hello <bx id="1" type="bold"/>World<ex id="1"/>`
2. `create_trans_unit()` calls `_escape_xml()` which converts `<` → `&lt;` and `>` → `&gt;`
3. The inline elements become escaped text: `Hello &lt;bx id="1" type="bold"/&gt;World&lt;ex id="1"/&gt;`
4. This is stored as plain text in the XLIFF, NOT as actual XML elements

**Impact**: When ORF reads the XLIFF, it will see `&lt;bx` instead of `<bx>` - the inline formatting is lost.

**Fix Required**: See Task 8a below.

---

## Context

### The Problem

OPP currently extracts text from paragraphs using library-specific text properties which concatenate all runs into a single string, losing inline formatting information:

```python
# DOCX (docx.py line 79):
text = para.text.strip()  # "Hello World" - bold is gone

# EPUB/HTML (epub.py line 155):
element_text = element.get_text(separator=" ", strip=True)  # loses <strong>/<em>
```

**Result**: Trans-unit contains only `"Hello World"` with no indication that "World" was bold. When ORF backfills the translation, there's no way to apply bold formatting.

### The Solution

Track formatting properties during extraction and encode them as **XLIFF inline elements** (`<bx>`, `<ex>`) in the generated XLIFF file.

### Why This Works

1. **XLIFF inline elements** - XLIFF 1.x has built-in inline codes (`<bx>`, `<ex>`) for formatting markers (not a separate "OL" system)
2. **Standard XLIFF format** - Inline elements `<bx>`, `<ex>` are valid XLIFF 1.x XML elements, not escaped text
3. **ORF backfill** - ORF converts XLIFF inline elements back to native formatting

**Important**: The OPP implementation must output `<bx>` as **actual XML elements**, not as escaped text like `&lt;bx`. translate-toolkit's `xlifffile` stores text content, so we need to manipulate the XML DOM directly to preserve inline element structure.

### Format Support Matrix

| Format | Extractor | Inline Source | Status |
|--------|-----------|--------------|--------|
| **DOCX** | `docx.py` | `<w:r>` with `<w:rPr>` | ✅ Done |
| **PPTX** | `pptx.py` | Text runs with font properties | ✅ Done |
| **EPUB** | `epub.py` | HTML `<strong>`, `<em>` | ✅ Done |
| **HTML** | `html.py` | HTML `<strong>`, `<em>`, `<b>`, `<i>`, `<u>` | ✅ Done |

---

## XLIFF Inline Element Format

OPP must use XLIFF 1.x inline codes to mark formatting:

| Source Property | XLIFF Begin | XLIFF End | Example |
|----------------|-------------|-----------|---------|
| Bold | `<bx id="N" type="bold"/>` | `<ex id="N"/>` | `Hello <bx id="1" type="bold"/>World<ex id="1"/>` |
| Italic | `<bx id="N" type="italic"/>` | `<ex id="N"/>` | `Hello <bx id="1" type="italic"/>World<ex id="1"/>` |
| Underline | `<bx id="N" type="underline"/>` | `<ex id="N"/>` | `Hello <bx id="1" type="underline"/>World<ex id="1"/>` |
| Strikethrough | `<bx id="N" type="strike"/>` | `<ex id="N"/>` | `Hello <bx id="1" type="strike"/>World<ex id="1"/>` |
| Combined | `<bx id="N" type="bold,italic"/>` | `<ex id="N"/>` | `<bx id="1" type="bold,italic"/>World<ex id="1"/>` |

### Correct XLIFF Output

```xml
<!-- CORRECT (inline elements as actual XML) -->
<trans-unit id="1">
  <source>Hello <bx id="1" type="bold"/>World<ex id="1"/></source>
</trans-unit>
```

### Buggy XLIFF Output (Current)

```xml
<!-- BUGGY (inline elements escaped as text) -->
<trans-unit id="1">
  <source>Hello &lt;bx id="1" type="bold"/&gt;World&lt;ex id="1"/&gt;</source>
</trans-unit>
```

---

## Data Structure Changes

### 1. New Dataclass: `RunData` ✅ DONE

**File**: `src/opp/utils/dataclasses.py` (lines 20-37)

```python
@dataclass
class RunData:
    """A text run with formatting properties."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_size: Optional[int] = None
    font_name: Optional[str] = None
    color: Optional[str] = None

@dataclass
class ParagraphData:
    text: str
    style: Optional[str] = None
    level: Optional[int] = None
    runs: List[RunData] = field(default_factory=list)
```

### 2. Extended `XLIFFTransUnit` ✅ DONE

**File**: `src/opp/xliff/xliff_dataclasses.py` (lines 23-43)

```python
@dataclass
class InlineElement:
    """An inline formatting element in XLIFF."""
    id: str
    type: str                    # "bold", "italic", "underline", etc.
    position: int                # Character position in source text
    text_covered: Optional[str] = None

@dataclass
class XLIFFTransUnit:
    id: str
    source: str
    source_language: str
    target: Optional[str] = None
    target_language: Optional[str] = None
    location: Optional[str] = None
    context: Optional[str] = None
    state: Optional[XLIFFUnitState] = None
    translate: bool = True
    inline_elements: List[InlineElement] = field(default_factory=list)
```

---

## Task Decomposition

### Wave 1: Data Structures ✅ DONE

| Task | File | Description | Status |
|------|------|-------------|--------|
| **1** | `utils/dataclasses.py` | Add `RunData` dataclass and `runs` field to `ParagraphData` | ✅ Done |
| **2** | `xliff/xliff_dataclasses.py` | Add `InlineElement` dataclass and `inline_elements` field to `XLIFFTransUnit` | ✅ Done |

### Wave 2: DOCX Extraction ✅ DONE

| Task | File | Description | Status |
|------|------|-------------|--------|
| **3** | `extractors/docx.py` | Add `extract_runs()` method to parse `<w:r>` elements with `<w:rPr>` | ✅ Done |
| **4** | `extractors/docx.py` | Modify `extract_paragraphs()` to populate `runs` field | ✅ Done |

### Wave 6: XLIFF Generation ✅ FIXED

| Task | File | Description | Status |
|------|------|-------------|--------|
| **8** | `xliff/generator.py` | Add `encode_inline_elements()` to convert `runs` to XLIFF markup | ✅ Done |
| **9** | `xliff/generator.py` | Modify `from_extraction_result()` to use inline-aware encoding | ✅ Done |
| **8a** | `xliff/generator.py` | **FIX BUG**: Add `_escape_xml_for_xliff()` + XML DOM manipulation to preserve `<bx>`/`<ex>` tags | ✅ Done |
| **8b** | `xliff/generator.py` | **FIX BUG**: Add `from __future__ import annotations` to fix type annotation scoping | ✅ Done |

### Wave 3: PPTX Extraction ✅ DONE

| Task | File | Description | Category | Status |
|------|------|-------------|----------|--------|
| **5a** | `extractors/pptx.py` | Add `extract_runs()` method for PPTX text runs | `unspecified-high` | ✅ Done |
| **5b** | `extractors/pptx.py` | Modify `extract_shapes()` to populate `runs` field | `unspecified-high` | ✅ Done |

### Wave 4: EPUB Extraction ✅ DONE

| Task | File | Description | Category | Status |
|------|------|-------------|----------|--------|
| **6a** | `extractors/epub.py` | Add `extract_runs()` method to parse HTML `<strong>`, `<em>` | `unspecified-high` | ✅ Done |
| **6b** | `extractors/epub.py` | Modify `_parse_html_elements()` to populate `runs` field | `unspecified-high` | ✅ Done |

### Wave 5: HTML Extraction ✅ DONE

| Task | File | Description | Category | Status |
|------|------|-------------|----------|--------|
| **7a** | `extractors/html.py` | Add `extract_runs()` method to parse HTML `<strong>`, `<em>`, `<b>`, `<i>`, `<u>` | `unspecified-high` | ✅ Done |
| **7b** | `extractors/html.py` | Modify `_extract_element()` to populate `runs` field | `unspecified-high` | ✅ Done |

### Wave 7: Testing ✅ DONE

| Task | File | Description | Category | Status |
|------|------|-------------|----------|--------|
| **10** | `tests/test_docx_run_extraction.py` | UTDD for DOCX `extract_runs()` | `quick` | ✅ Done |
| **11** | `tests/test_pptx_run_extraction.py` | UTDD for PPTX `extract_runs()` | `quick` | ✅ Done |
| **12** | `tests/test_epub_run_extraction.py` | UTDD for EPUB `extract_runs()` | `quick` | ✅ Done |
| **13** | `tests/test_html_run_extraction.py` | UTDD for HTML `extract_runs()` | `quick` | ✅ Done |
| **14** | `tests/test_xliff_inline_generation.py` | UTDD for inline element encoding | `quick` | ✅ Done |
| **15** | `tests/test_integration_inline.py` | Integration test - format→XLIFF preserves formatting | `quick` | ✅ Done |

---

## Task 8a: Fix Inline Element Escaping Bug

### Problem Analysis

**Two bugs found in `xliff/generator.py`:**

**Bug 1: Type annotation scoping issue** (Lines 4, 64)
- `encode_inline_elements()` uses `List[RunData]` in its signature
- But `RunData` is only imported inside the method body (line 74)
- Python evaluates type annotations at class definition time → `NameError: name 'RunData' is not defined`
- **Fix**: Add `from __future__ import annotations` to defer annotation evaluation

**Bug 2: `_escape_xml()` breaks inline elements** (Lines 54-61, 116-137)
- `encode_inline_elements()` produces source text like: `Hello <bx id="1" type="bold"/>World<ex id="1"/>`
- `create_trans_unit()` calls `_escape_xml()` which converts `<` → `&lt;` and `>` → `&gt;`
- The inline elements become escaped text: `Hello &lt;bx id="1" type="bold"/&gt;World&lt;ex id="1"/&gt;`
- **Fix**: Add `_escape_xml_for_xliff()` that preserves inline element tags

### Solution Options

#### Option A: Use `rich_source` API (Recommended)

translate-toolkit supports `rich_source` property for inline elements:

```python
# Instead of escaping, set inline elements via rich_source
def create_trans_unit(self, unit: XLIFFTransUnit):
    # Set plain text source (without inline markup)
    source = self._escape_xml(self._filter_control_chars(unit.source))
    xliff_unit = self._store.addsourceunit(source)
    
    # If unit has inline elements, set them via rich_source
    if hasattr(unit, 'inline_elements') and unit.inline_elements:
        self._set_rich_source_with_inline(xliff_unit, unit)
```

This requires understanding translate-toolkit's `strelem_to_xml()` function to convert inline elements to XML DOM nodes.

#### Option B: Protect Inline Tags Before Escaping (Robust)

```python
@staticmethod
def _escape_xml_for_xliff(text: str) -> str:
    """Escape XML special characters, but preserve XLIFF inline element tags.

    XLIFF 1.x inline elements like <bx>, <ex>, <g>, <mrk>, <x>, <ph>
    must be preserved as literal XML, not escaped.

    Uses a robust protection mechanism that handles edge cases:
    - Placeholders use GUID-style strings unlikely to appear in content
    - Replacement is applied character-by-character to avoid regex issues
    """
    if not text:
        return text

    # XLIFF inline element patterns
    inline_open_tags = ['<bx ', '<ex ', '<g ', '<mrk ', '<x ', '<ph ']
    inline_close_tags = ['</bx>', '</ex>', '</g>', '</mrk>', '</x>', '</ph>']
    inline_self_closing = ['<bx', '<ex', '<g', '<mrk', '<x', '<ph']

    # Find and protect all inline tags
    protected_ranges = []
    search_pos = 0

    while search_pos < len(text):
        # Find next '<' character
        next_tag_start = text.find('<', search_pos)
        if next_tag_start == -1:
            break

        # Find corresponding closing '>'
        next_tag_end = text.find('>', next_tag_start)
        if next_tag_end == -1:
            # Malformed tag - treat rest as text
            break

        tag_content = text[next_tag_start:next_tag_end + 1]
        tag_lower = tag_content.lower()

        # Check if this is an inline element tag
        is_inline = (
            any(tag_lower.startswith(t) for t in inline_open_tags) or
            any(tag_lower.startswith(t) for t in inline_self_closing) or
            any(tag_lower.startswith(t) for t in inline_close_tags)
        )

        if is_inline:
            protected_ranges.append((next_tag_start, next_tag_end + 1, tag_content))
            search_pos = next_tag_end + 1
        else:
            search_pos = next_tag_start + 1

    if not protected_ranges:
        # No inline tags found - escape everything normally
        return _escape_xml_static(text)

    # Build result with protection
    result_parts = []
    prev_end = 0

    for start, end, tag in protected_ranges:
        # Add escaped text before this tag
        result_parts.append(_escape_xml_static(text[prev_end:start]))
        # Add inline tag as-is (no escaping)
        result_parts.append(tag)
        prev_end = end

    # Add remaining text
    result_parts.append(_escape_xml_static(text[prev_end:]))

    return ''.join(result_parts)


@staticmethod
def _escape_xml_static(text: str) -> str:
    """Static helper - escape XML special characters without inline handling."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
```

**Key improvements**:
1. Uses position-based extraction instead of string.replace
2. Validates each `<...>` tag before protecting
3. Only protects tags that actually look like XLIFF inline elements
4. Doesn't use placeholder strings that could collide with content

### Recommended Fix Implementation

**File**: `src/opp/xliff/generator.py`

**Note**: There's also a **type annotation scoping issue** in the current code. The `encode_inline_elements()` method at line 64 uses `List[RunData]` in its signature, but `RunData` is only imported inside the method body (line 74). This causes a `NameError` when the module is loaded because Python evaluates type annotations at class definition time. The fix requires adding `from __future__ import annotations` at the top of the file to defer annotation evaluation.

```python
from __future__ import annotations  # Required for type annotations with forward references

from pathlib import Path
from typing import List, TYPE_CHECKING

from translate.storage.xliff import xlifffile

from opp.utils.dataclasses import ExtractionResult
from opp.xliff import XLIFFFileAttributes, XLIFFTransUnit

if TYPE_CHECKING:
    from opp.utils.dataclasses import RunData
    from opp.xliff.xliff_dataclasses import InlineElement


class XLIFFFileGenerator:
    # ... existing methods ...

    @staticmethod
    def _escape_xml_for_xliff(text: str) -> str:
        """Escape XML special characters, but preserve XLIFF inline element tags.

        XLIFF 1.x inline elements like <bx>, <ex>, <g>, <mrk>, <x>, <ph>
        must be preserved as literal XML, not escaped.

        Uses a robust protection mechanism that handles edge cases:
        - Position-based extraction avoids regex issues
        - Validates each <...> tag before protecting
        - Only protects tags that actually look like XLIFF inline elements
        """
        if not text:
            return text

        # XLIFF inline element patterns
        inline_open_tags = ['<bx ', '<ex ', '<g ', '<mrk ', '<x ', '<ph ']
        inline_close_tags = ['</bx>', '</ex>', '</g>', '</mrk>', '</x>', '</ph>']
        inline_self_closing = ['<bx', '<ex', '<g', '<mrk', '<x', '<ph']

        # Find and protect all inline tags
        protected_ranges = []
        search_pos = 0

        while search_pos < len(text):
            next_tag_start = text.find('<', search_pos)
            if next_tag_start == -1:
                break

            next_tag_end = text.find('>', next_tag_start)
            if next_tag_end == -1:
                break

            tag_content = text[next_tag_start:next_tag_end + 1]
            tag_lower = tag_content.lower()

            is_inline = (
                any(tag_lower.startswith(t) for t in inline_open_tags) or
                any(tag_lower.startswith(t) for t in inline_self_closing) or
                any(tag_lower.startswith(t) for t in inline_close_tags)
            )

            if is_inline:
                protected_ranges.append((next_tag_start, next_tag_end + 1, tag_content))
                search_pos = next_tag_end + 1
            else:
                search_pos = next_tag_start + 1

        if not protected_ranges:
            return _escape_xml_static(text)

        result_parts = []
        prev_end = 0

        for start, end, tag in protected_ranges:
            result_parts.append(_escape_xml_static(text[prev_end:start]))
            result_parts.append(tag)
            prev_end = end

        result_parts.append(_escape_xml_static(text[prev_end:]))
        return ''.join(result_parts)


    @staticmethod
    def _escape_xml_static(text: str) -> str:
        """Static helper - escape XML special characters without inline handling."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
```

### Alternative: Use lxml DOM Manipulation

If the tag-protection approach proves problematic, consider using lxml to manipulate the XLIFF DOM directly:

```python
from lxml import etree

def create_trans_unit_with_inline(self, unit: XLIFFTransUnit) -> None:
    """Create trans-unit with proper inline element handling."""
    # Create the trans-unit element directly
    trans_unit = etree.Element('trans-unit')
    trans_unit.set('id', unit.id)

    # Create source element with inline elements as actual XML
    source_elem = etree.SubElement(trans_unit, 'source')

    # Parse the source text which may contain inline elements
    self._add_inline_elements_to_source(source_elem, unit.source, unit.inline_elements)

    # Add to store via DOM manipulation
    self._store.getroot().find('body').append(trans_unit)
```

This approach requires deeper integration with translate-toolkit's internal structure.

---

## Key Implementation Details

### Task 5a: PPTX `extract_runs()`

**File**: `src/opp/extractors/pptx.py`

python-pptx text runs are in `text_frame.paragraphs[i].runs[j]`:
- `run.font.bold`
- `run.font.italic`
- `run.font.underline`
- `run.font.strike`
- `run.font.size`
- `run.font.name`

```python
def extract_runs(self, shape) -> List[RunData]:
    """Extract runs with formatting from a shape's text frame."""
    from opp.utils.dataclasses import RunData
    
    runs = []
    if not shape.has_text_frame:
        return runs
    
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            text = run.text
            if not text or not text.strip():
                continue
            
            font = run.font
            run_data = RunData(
                text=text,
                bold=bool(font.bold) if font.bold else False,
                italic=bool(font.italic) if font.italic else False,
                underline=bool(font.underline) if font.underline else False,
                strike=bool(font.strike) if font.strike else False,
            )
            runs.append(run_data)
    
    return runs
```

### Task 5b: PPTX `extract_shapes()` modification

```python
def extract_shapes(self, slide) -> List[ParagraphData]:
    result = []
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            result.extend(self._flatten_group(shape))
        elif shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                runs = self.extract_runs(shape)
                plain_text = ''.join(r.text for r in runs)
                
                if self._is_title_shape(shape):
                    result.append(ParagraphData(
                        text=plain_text,
                        style="Heading 1",
                        level=1,
                        runs=runs,
                    ))
                else:
                    result.append(ParagraphData(
                        text=plain_text,
                        style=shape.shape_type.name if hasattr(shape.shape_type, 'name') else None,
                        level=None,
                        runs=runs,
                    ))
    return result
```

### Task 6a: EPUB `extract_runs()`

**File**: `src/opp/extractors/epub.py`

BeautifulSoup elements have `.find_all()` for child elements. HTML tags:
- `<strong>`, `<b>` → bold
- `<em>`, `<i>` → italic
- `<u>` → underline

```python
def extract_runs(self, element) -> List[RunData]:
    """Extract runs with formatting from a BeautifulSoup element."""
    from opp.utils.dataclasses import RunData
    
    runs = []
    
    for child in element.children:
        if hasattr(child, 'name') and child.name:
            bold = child.name in ('strong', 'b')
            italic = child.name in ('em', 'i')
            underline = child.name == 'u'
            
            text = child.get_text()
            if text and text.strip():
                runs.append(RunData(
                    text=text,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                ))
            
            if child.name in ('span', 'a', 'strong', 'em', 'b', 'i', 'u'):
                child_runs = self.extract_runs(child)
                runs.extend(child_runs)
    
    return runs
```

### Task 6b: EPUB `_parse_html_elements()` modification

```python
def _parse_html_elements(self, html_content: str) -> List[ParagraphData]:
    # ... existing code ...
    for tag in heading_tags | {'p'}:
        for element in soup.find_all(tag):
            if not _should_process_element(element, heading_tags):
                continue
            element_text = element.get_text(separator=" ", strip=True)
            if element_text:
                runs = self.extract_runs(element)
                plain_text = ''.join(r.text for r in runs) if runs else element_text
                
                if tag in heading_tags:
                    level = int(tag[1])
                    paragraphs.append(ParagraphData(
                        text=plain_text,
                        style=f"Heading {level}",
                        level=level,
                        runs=runs,
                    ))
                else:
                    paragraphs.append(ParagraphData(
                        text=plain_text,
                        style="Normal",
                        level=None,
                        runs=runs,
                    ))
    return paragraphs
```

### Task 7a: HTML `extract_runs()`

**File**: `src/opp/extractors/html.py`

Similar to EPUB but handles more tags:
- `<strong>`, `<b>` → bold
- `<em>`, `<i>` → italic
- `<u>` → underline
- `<s>`, `<del>` → strike

```python
def extract_runs(self, element) -> List[RunData]:
    """Extract runs with formatting from a BeautifulSoup element."""
    from opp.utils.dataclasses import RunData
    
    runs = []
    
    for child in element.children:
        if hasattr(child, 'name') and child.name:
            bold = child.name in ('strong', 'b')
            italic = child.name in ('em', 'i')
            underline = child.name == 'u'
            strike = child.name in ('s', 'del')
            
            text = child.get_text()
            if text and text.strip():
                runs.append(RunData(
                    text=text,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    strike=strike,
                ))
            
            if child.name in ('span', 'a', 'strong', 'em', 'b', 'i', 'u', 's', 'del'):
                child_runs = self.extract_runs(child)
                runs.extend(child_runs)
    
    return runs
```

---

## Backward Compatibility

### No `runs` field

If `ParagraphData` has empty `runs` list, `from_extraction_result()` falls back:
```python
if hasattr(para, 'runs') and para.runs:
    source, inline_elements = encode_inline_elements(para.runs)
else:
    source = para.text
    inline_elements = []
```

### Non-Rich-Text Extractors

PDF, CSV, XLSX, JSON, etc. produce plain text without inline formatting:
- Leave `runs` empty
- Generate XLIFF without inline elements (plain text only)
- ORF backfill works without formatting

---

## Success Criteria

1. **Unit tests pass**: All format-specific tests pass
2. **XLIFF validation**: Generated XLIFF has `<bx>` and `<ex>` as actual XML elements (not escaped text)
3. **Inline elements preserved**: `<bx>` and `<ex>` appear in source for all formats
4. **Backward compatible**: Plain-text extractors still work
5. **Integration tests**: Each format→XLIFF preserves formatting

---

## Test Cases

### `tests/test_xliff_inline_generation.py`

```python
def test_encode_inline_elements_creates_bx_tags():
    """Bold run creates <bx> and <ex> tags in source."""
    runs = [
        RunData(text="Hello "),
        RunData(text="World", bold=True)
    ]
    source, elements = XLIFFFileGenerator.encode_inline_elements(runs)
    
    assert '<bx id="1" type="bold"/>' in source
    assert '<ex id="1"/>' in source
    assert elements[0].type == "bold"

def test_escape_xml_preserves_inline_tags():
    """_escape_xml() must NOT escape <bx> and <ex> tags."""
    text = 'Hello <bx id="1" type="bold"/>World<ex id="1"/>'
    escaped = XLIFFFileGenerator._escape_xml_for_xliff(text)
    
    assert '<bx' in escaped  # NOT &lt;bx
    assert '&lt;' not in escaped  # No escaped angle brackets in inline tags
```

### `tests/test_integration_inline.py`

```python
def test_docx_bold_roundtrip():
    """DOCX bold → OPP → XLIFF → check <bx> elements exist."""
    # 1. Extract DOCX with bold text
    extractor = DOCXExtractor()
    result = extractor.extract(Path("bold.docx"))
    
    # 2. Generate XLIFF
    generator = XLIFFFileGenerator.from_extraction_result(
        result, source_lang="en", target_lang="zh")
    xliff_bytes = generator.to_bytes()
    xliff_str = xliff_bytes.decode('utf-8')
    
    # 3. Verify <bx> tags are present as XML elements (not escaped)
    assert '<bx id="1" type="bold"/>' in xliff_str
    assert '&lt;bx' not in xliff_str  # Should NOT be escaped
```

---

## File Changes Summary

| File | Change Type | Lines | Status |
|------|------------|-------|--------|
| `src/opp/utils/dataclasses.py` | Modify | +15 | ✅ Done |
| `src/opp/xliff/xliff_dataclasses.py` | Modify | +15 | ✅ Done |
| `src/opp/extractors/docx.py` | Modify | +30 | ✅ Done |
| `src/opp/extractors/pptx.py` | Modify | +40 | ✅ Done |
| `src/opp/extractors/epub.py` | Modify | +45 | ✅ Done |
| `src/opp/extractors/html.py` | Modify | +45 | ✅ Done |
| `src/opp/xliff/generator.py` | Modify | +80 | ✅ Done |
| `tests/test_docx_run_extraction.py` | New | +200 | ✅ Done |
| `tests/test_pptx_run_extraction.py` | New | +150 | ✅ Done |
| `tests/test_epub_run_extraction.py` | New | +160 | ✅ Done |
| `tests/test_html_run_extraction.py` | New | +160 | ✅ Done |
| `tests/test_xliff_inline_generation.py` | New | +180 | ✅ Done |
| `tests/test_integration_inline.py` | New | +150 | ✅ Done |

---

## Timeline

| Wave | Tasks | Status | Blocker |
|------|-------|--------|---------|
| Wave 1: Data Structures | 1-2 | ✅ Done | None |
| Wave 2: DOCX | 3-4 | ✅ Done | None |
| Wave 6.5: Bug Fix | 8a, 8b | ✅ Done | None |
| Wave 3: PPTX | 5a-5b | ✅ Done | None |
| Wave 4: EPUB | 6a-6b | ✅ Done | None |
| Wave 5: HTML | 7a-7b | ✅ Done | None |
| Wave 7: Testing | 10-15 | ✅ Done | None |

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| **Bug 1: Type annotation scoping** | **CRITICAL** | Add `from __future__ import annotations` at top of generator.py |
| **Bug 2: `_escape_xml()` breaks inline elements** | **CRITICAL** | Use `_escape_xml_for_xliff()` that preserves `<bx>`/`<ex>` tags |
| python-docx run properties | Low | Well-documented API |
| python-pptx font properties | Medium | Some properties may be None |
| BeautifulSoup element traversal | Medium | Nested tag handling complexity |
| Edge case: `<bx>` inside attribute values | Low | Tag detection uses position, not regex |
| Backward compatibility | Low | Graceful fallback if no `runs` |

---

## Commit Strategy

```bash
# Wave 1: Data structures
git commit -m "feat(dataclasses): add RunData and InlineElement dataclasses"

# Wave 2: DOCX extraction
git commit -m "feat(docx): extract runs with formatting properties"

# Wave 6.5: Bug fix (2 bugs)
# - Add from __future__ import annotations for type annotation scoping
# - Add _escape_xml_for_xliff() to preserve <bx>/<ex> tags
git commit -m "fix(xliff): preserve inline elements and fix type annotation scoping"

# Wave 3: PPTX extraction
git commit -m "feat(pptx): extract runs with formatting properties"

# Wave 4: EPUB extraction
git commit -m "feat(epub): extract runs from HTML elements"

# Wave 5: HTML extraction
git commit -m "feat(html): extract runs from HTML elements"

# Wave 7: Testing
git commit -m "test: add inline formatting extraction tests"
```

---

## Related Plans

- **ORF Phase 1 (Inline Formatting)**: `/mnt/d/贯维/Omni_Re_Formatter/.omo/plans/phase1-plan-inline-formatting.md` - ORF backfill to restore formatting from XLIFF inline elements
- **translate-toolkit research**: Confirmed via `uv run python` testing that `addsourceunit()` stores source as text content (not XML elements), and that `_escape_xml()` escapes `<bx>` to `&lt;bx`