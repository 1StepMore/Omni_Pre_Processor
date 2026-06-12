"""XLIFF file generator for translation workflows."""

from __future__ import annotations

from pathlib import Path
from typing import List, TYPE_CHECKING

from translate.storage.xliff import xlifffile

from opp.utils.dataclasses import ExtractionResult
from opp.xliff import XLIFFFileAttributes, XLIFFTransUnit

if TYPE_CHECKING:
    from opp.utils.dataclasses import RunData
    from opp.xliff.xliff_dataclasses import InlineElement


class XLIFFFileGenerator:
    """Generator for XLIFF translation files."""

    def __init__(self, attributes: XLIFFFileAttributes) -> None:
        """Initialize the generator with file attributes.

        Args:
            attributes: XLIFF file attributes (source/target languages, etc.)
        """
        self._attributes = attributes
        self._units: list[XLIFFTransUnit] = []
        self._store = xlifffile()
        self._store.setsourcelanguage(attributes.source_language)
        self._store.settargetlanguage(attributes.target_language)

    def set_file_attributes(self, attributes: XLIFFFileAttributes) -> None:
        """Reconfigure the XLIFF file attributes.

        This allows updating the file header settings after initialization.

        Args:
            attributes: New XLIFF file attributes
        """
        self._attributes = attributes
        self._store = xlifffile()
        self._store.setsourcelanguage(attributes.source_language)
        self._store.settargetlanguage(attributes.target_language)

    def add_unit(self, unit: XLIFFTransUnit) -> None:
        """Add a translation unit to the generator.

        Args:
            unit: The translation unit to add
        """
        self._units.append(unit)
        xliff_unit = self.create_trans_unit(unit)
        if unit.resname and xliff_unit is not None:
            # translate-toolkit has no setresname; use lxml directly.
            xliff_unit.xmlelement.set('resname', unit.resname)

    @staticmethod
    def _filter_control_chars(text: str) -> str:
        return "".join(c for c in text if ord(c) > 0x08)

    @staticmethod
    def _escape_xml_static(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    @staticmethod
    def _escape_xml_for_xliff(text: str) -> str:
        """Escape XML but preserve XLIFF inline elements.

        XLIFF inline elements are tags like <bx>, <ex>, <g>, <mrk>, <x>, <ph>.
        These should be preserved as-is in the output.

        Args:
            text: Text to escape

        Returns:
            Escaped text with inline elements preserved
        """
        inline_tags = {"bx", "ex", "g", "mrk", "x", "ph"}
        result = []
        pos = 0

        while pos < len(text):
            # Find next tag start
            tag_start = text.find("<", pos)
            if tag_start == -1:
                # No more tags, append rest as-is
                result.append(text[pos:])
                break

            # Append text before the tag (escaped)
            if tag_start > pos:
                result.append(XLIFFFileGenerator._escape_xml_static(text[pos:tag_start]))

            # Find corresponding tag end
            tag_end = text.find(">", tag_start)
            if tag_end == -1:
                # Malformed XML, treat rest as text
                result.append(text[tag_start:])
                break

            # Check if this is an inline element
            tag_content = text[tag_start + 1:tag_end]
            first_word = tag_content.split()[0] if tag_content else ""

            if first_word in inline_tags:
                result.append(text[tag_start:tag_end + 1])
            else:
                result.append(XLIFFFileGenerator._escape_xml_static(text[tag_start:tag_end + 1]))

            pos = tag_end + 1

        return "".join(result)

    @staticmethod
    def encode_inline_elements(runs: list[RunData]) -> tuple[str, list[InlineElement]]:
        """Convert run formatting to XLIFF inline markup.

        Args:
            runs: List of RunData with text and formatting properties

        Returns:
            Tuple of (source_text_with_markup, list of InlineElement metadata)
        """
        from opp.xliff.xliff_dataclasses import InlineElement

        inline_counter = 0
        result_parts = []
        inline_elements = []

        for run in runs:
            formatting_types = []

            # Check each formatting type
            if run.bold:
                formatting_types.append("bold")
            if run.italic:
                formatting_types.append("italic")
            if run.underline:
                formatting_types.append("underline")
            if run.strike:
                formatting_types.append("strike")

            # If any formatting, add inline markers
            if formatting_types:
                inline_counter += 1
                elem_id = str(inline_counter)
                type_str = ",".join(formatting_types)

                inline_elements.append(InlineElement(
                    id=elem_id,
                    type=type_str,
                    position=len(''.join(result_parts)),
                    text_covered=run.text,
                ))

                result_parts.append(f'<bx id="{elem_id}" type="{type_str}"/>')

            result_parts.append(run.text)

            # Close inline markers after text
            if formatting_types:
                result_parts.append(f'<ex id="{elem_id}"/>')

        return ''.join(result_parts), inline_elements

    def create_trans_unit(self, unit: XLIFFTransUnit):

        # Check if unit has inline elements that need XML DOM manipulation
        if hasattr(unit, 'inline_elements') and unit.inline_elements:
            # Create unit with placeholder text
            xliff_unit = self._store.addsourceunit('placeholder')
            xliff_unit.setid(unit.id)

            # Get the XML element and modify it directly
            elem = xliff_unit.xmlelement
            ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.1'}
            source_elem = elem.find('xliff:source', ns)

            if source_elem is None:
                # Fallback if namespace lookup fails
                source_elem = elem.find('source')

            if source_elem is not None:
                # Clear existing content including placeholder text
                source_elem.text = None
                for child in list(source_elem):
                    source_elem.remove(child)

                # Build source content from unit.source which contains inline markup
                self._build_source_with_inline(source_elem, unit.source)

            # Preserve whitespace on <source> and <target> so downstream textContent
            # readers don't pull in unintended indentation between siblings.
            for _elem_name_inline in ("source", "target"):
                _elem_inline = elem.find(
                    f'{{urn:oasis:names:tc:xliff:document:1.1}}{_elem_name_inline}'
                ) or elem.find(_elem_name_inline)
                if _elem_inline is not None:
                    _elem_inline.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

            if unit.location:
                xliff_unit.addlocation(unit.location)
            if unit.context:
                xliff_unit.addnote(unit.context, origin="OPP")
            if unit.state and unit.state.value == "approved":
                xliff_unit.markapproved(True)

            return xliff_unit

        # Original behavior for plain text (no inline elements)
        source = self._escape_xml_for_xliff(self._filter_control_chars(unit.source))
        target = None
        if unit.target:
            target = self._escape_xml_static(self._filter_control_chars(unit.target))

        xliff_unit = self._store.addsourceunit(source)
        xliff_unit.setid(unit.id)

        # Preserve whitespace on <source> and <target> so downstream textContent
        # readers don't pull in unintended indentation between siblings.
        for _elem_name in ("source", "target"):
            _elem = xliff_unit.xmlelement.find(_elem_name)
            if _elem is not None:
                _elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        if target:
            xliff_unit.target = target

        if unit.location:
            xliff_unit.addlocation(unit.location)

        if unit.context:
            xliff_unit.addnote(unit.context, origin="OPP")

        if unit.state and unit.state.value == "approved":
            xliff_unit.markapproved(True)

        return xliff_unit

    def _build_source_with_inline(self, source_elem, source_text: str):
        """Build source element with inline elements as actual XML children."""
        from lxml import etree

        # Parse the source_text which contains inline element markup
        # Format: Text<bx id="N" type="fmt"/>Text<ex id="N"/>Text
        inline_tags = {'bx', 'ex', 'g', 'mrk', 'x', 'ph'}

        pos = 0
        text_content = []

        while pos < len(source_text):
            # Find next '<' character
            tag_start = source_text.find('<', pos)
            if tag_start == -1:
                # No more tags, append remaining text
                text_content.append(source_text[pos:])
                break

            # Append text before the tag
            if tag_start > pos:
                text_content.append(source_text[pos:tag_start])

            # Find end of tag
            tag_end = source_text.find('>', tag_start)
            if tag_end == -1:
                # Malformed, treat rest as text
                text_content.append(source_text[pos:])
                break

            tag_content = source_text[tag_start + 1:tag_end]
            first_word = tag_content.split()[0] if tag_content else ""

            if first_word in inline_tags:
                # Check if this is a self-closing tag (ends with /)
                is_self_closing = tag_content.rstrip().endswith('/')
                
                # This is an inline element tag - add it as XML child
                if text_content:
                    # Add accumulated text to the appropriate node
                    # First text segment goes to source_elem.text
                    # Subsequent text segments go to the tail of the previous element
                    if source_elem.text is None and len(source_elem) == 0:
                        # First text segment - set source_elem.text
                        source_elem.text = ''.join(text_content)
                    else:
                        # Subsequent text - set tail of last child element
                        if len(source_elem) > 0:
                            source_elem[-1].tail = ''.join(text_content)
                        else:
                            source_elem.text = ''.join(text_content)
                    text_content = []

                # Parse attributes from tag content using regex
                # This handles cases like 'bx id="1" type="bold"/' properly
                import re
                attrs = {}
                for match in re.finditer(r'(\w+)="([^"]*)"', tag_content):
                    key, val = match.groups()
                    # Strip any trailing / from the value
                    val = val.rstrip('/')
                    attrs[key] = val

                # Create the inline element
                if first_word in ('bx', 'ex', 'g', 'mrk', 'x', 'ph'):
                    new_elem = etree.SubElement(source_elem, first_word)
                    for key, val in attrs.items():
                        new_elem.set(key, val)
                    
                    # For self-closing tags, immediately look for following text as tail
                    # Don't wait for the next tag to assign tail
                    if is_self_closing:
                        next_pos = tag_end + 1
                        # Look for text immediately following the self-closing tag
                        next_tag_pos = source_text.find('<', next_pos)
                        if next_tag_pos == -1:
                            # No more tags, remaining text is tail of this element
                            remaining = source_text[next_pos:].strip()
                            if remaining:
                                new_elem.tail = remaining
                            pos = len(source_text)
                        elif next_tag_pos > next_pos:
                            # There's text between this tag and the next
                            text_after = source_text[next_pos:next_tag_pos]
                            if text_after.strip():
                                new_elem.tail = text_after
                            pos = next_tag_pos
                        else:
                            # Next tag immediately follows (no text in between)
                            pos = next_pos
                        continue
            else:
                # Not an inline tag, treat as text
                text_content.append(source_text[tag_start:tag_end + 1])

            pos = tag_end + 1

        # Add any remaining text
        if text_content:
            if len(source_elem):
                # Already has children, add as tail of last child
                source_elem[-1].tail = ''.join(text_content)
            else:
                source_elem.text = ''.join(text_content)

    def generate_xliff_1_2(self) -> bytes:
        """Generate XLIFF 1.2 compliant XML bytes.

        Returns:
            Bytes representation of the XLIFF 1.2 file
        """
        raw_bytes = bytes(self._store)
        return self._upgrade_namespace_to_1_2(raw_bytes)

    @staticmethod
    def _upgrade_namespace_to_1_2(xliff_bytes: bytes) -> bytes:
        ns_1_1 = b"urn:oasis:names:tc:xliff:document:1.1"
        ns_1_2 = b"urn:oasis:names:tc:xliff:document:1.2"
        result = xliff_bytes.replace(ns_1_1, ns_1_2)
        result = result.replace(b'version="1.1"', b'version="1.2"')
        return result

    def to_bytes(self) -> bytes:
        """Convert the XLIFF content to bytes.

        Returns:
            Bytes representation of the XLIFF file
        """
        return self.generate_xliff_1_2()

    def write_to_file(self, path: Path) -> None:
        """Write the XLIFF content to a file.

        Args:
            path: Path to write the file to
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_bytes())

    @classmethod
    def from_extraction_result(
        cls,
        result: ExtractionResult,
        source_lang: str,
        target_lang: str,
    ) -> "XLIFFFileGenerator":
        """Create a generator from an extraction result.

        Args:
            result: The extraction result containing paragraphs
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'fr')

        Returns:
            Configured XLIFFFileGenerator instance
        """
        attributes = XLIFFFileAttributes(
            source_language=source_lang,
            target_language=target_lang,
        )
        generator = cls(attributes)

        for idx, para in enumerate(result.paragraphs):
            # Check if paragraph has run-level formatting
            if hasattr(para, 'runs') and para.runs:
                # Use inline element encoding
                source, inline_elements = cls.encode_inline_elements(para.runs)
            else:
                # Backward compatibility: plain text
                source = para.text
                inline_elements = []

            # ULTRAREADY-FIX (2026-06-08): every trans-unit must carry a
            # non-None resname so ORF's B.2 position-based backfill can
            # locate it in the source DOCX. Pre-fix code assigned
            # resname=None for non-body content (table cells, header/
            # footer paragraphs), which silently produced empty cells in
            # the final DOCX because the backfill pass wiped the cell
            # content without ever finding a target paragraph to
            # inject the LLM translation into. Body paragraphs use the
            # `para_index_N` prefix (B.2 contract); non-body content
            # uses `non_body_N` so ORF's resname-prefix dispatch can
            # distinguish the two paths.
            body_idx = getattr(para, 'para_index_in_body', None)
            if body_idx is not None:
                resname = f"para_index_{body_idx}"
            else:
                resname = f"non_body_{idx}"

            unit = XLIFFTransUnit(
                id=str(idx + 1),
                source=source,
                source_language=source_lang,
                inline_elements=inline_elements,
                resname=resname,
            )
            generator.add_unit(unit)

        return generator