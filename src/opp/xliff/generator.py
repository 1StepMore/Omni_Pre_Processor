"""XLIFF file generator for translation workflows."""

from pathlib import Path

from translate.storage.xliff import xlifffile

from opp.utils.dataclasses import ExtractionResult
from opp.xliff import XLIFFFileAttributes, XLIFFTransUnit


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
        self.create_trans_unit(unit)

    @staticmethod
    def _filter_control_chars(text: str) -> str:
        return "".join(c for c in text if ord(c) > 0x08)

    @staticmethod
    def _escape_xml(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def create_trans_unit(self, unit: XLIFFTransUnit):
        source = self._escape_xml(self._filter_control_chars(unit.source))
        target = None
        if unit.target:
            target = self._escape_xml(self._filter_control_chars(unit.target))

        xliff_unit = self._store.addsourceunit(source)
        xliff_unit.setid(unit.id)

        if target:
            xliff_unit.target = target

        if unit.location:
            xliff_unit.addlocation(unit.location)

        if unit.context:
            xliff_unit.addnote(unit.context, origin="OPP")

        if unit.state and unit.state.value == "approved":
            xliff_unit.markapproved(True)

        return xliff_unit

    def generate_xliff_1_2(self) -> bytes:
        """Generate XLIFF 1.2 compliant XML bytes.

        Returns:
            Bytes representation of the XLIFF 1.2 file
        """
        return bytes(self._store)

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
            unit = XLIFFTransUnit(
                id=str(idx + 1),
                source=para.text,
                source_language=source_lang,
            )
            generator.add_unit(unit)

        return generator