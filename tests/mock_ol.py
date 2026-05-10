"""Mock OL (Localization) tool for testing OPP→OL integration."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"


class MockOLTool:
    """Mock OL tool that simulates translation by adding _translated suffix."""

    def __init__(self, source_lang: str = "en", target_lang: str = "fr"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate_xliff(self, input_path: Path, output_path: Path) -> bool:
        """Translate XLIFF file by adding translation suffixes."""
        try:
            tree = ET.parse(input_path)
            root = tree.getroot()

            ns_uri = self._get_ns(root)

            for trans_unit in root.iter():
                tag = trans_unit.tag
                if tag.endswith("}trans-unit") or tag == "trans-unit":
                    source_el = trans_unit.find(f"{{{ns_uri}}}source")
                    if source_el is not None and source_el.text:
                        translated_text = f"{source_el.text}_translated"

                        target_el = trans_unit.find(f"{{{ns_uri}}}target")
                        if target_el is None:
                            target_el = ET.SubElement(trans_unit, f"{{{ns_uri}}}target")
                        target_el.text = translated_text

            file_el = root.find(f"{{{ns_uri}}}file")
            if file_el is not None:
                file_el.set("target-language", self.target_lang)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            ns_uri = self._get_ns(root)

            output_text = ET.tostring(root, encoding="unicode")

            if "ns0:" in output_text:
                output_text = output_text.replace(f'xmlns:ns0="{ns_uri}"', f'xmlns="{ns_uri}"')
                output_text = output_text.replace("ns0:", "")

            output_path.write_text(output_text, encoding="UTF-8")

            return True

        except Exception as e:
            print(f"Error translating XLIFF: {e}", file=sys.stderr)
            return False

    def validate_translation(self, xliff_path: Path) -> tuple[bool, list[str]]:
        """Validate that translated XLIFF has target content."""
        errors = []

        try:
            tree = ET.parse(xliff_path)
            root = tree.getroot()

            ns_uri = self._get_ns(root)

            file_el = root.find(f"{{{ns_uri}}}file")
            if file_el is None:
                errors.append("No <file> element found in XLIFF")
                return False, errors

            target_lang = file_el.get("target-language")
            if not target_lang:
                errors.append("No target-language attribute found")

            trans_units = root.findall(f".//{{{ns_uri}}}trans-unit")
            if trans_units:
                for unit in trans_units:
                    source_el = unit.find(f"{{{ns_uri}}}source")
                    target_el = unit.find(f"{{{ns_uri}}}target")

                    if source_el is None:
                        errors.append(f"trans-unit {unit.get('id')} has no source element")
                        continue

                    if target_el is None:
                        errors.append(f"trans-unit {unit.get('id')} has no target element")
                        continue

                    if not target_el.text:
                        errors.append(f"trans-unit {unit.get('id')} has empty target")
                        continue

                    if "_translated" not in target_el.text:
                        errors.append(
                            f"trans-unit {unit.get('id')} target doesn't contain '_translated' suffix"
                        )

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"Validation error: {e}")
            return False, errors

    @staticmethod
    def _get_ns(root) -> str:
        tag = root.tag
        if tag.startswith("{"):
            brace_pos = tag.index("}")
            ns_from_tag = tag[1:brace_pos]
            if "xliff" in ns_from_tag:
                return ns_from_tag
        for uri in root.attrib.values():
            if "xliff" in uri:
                return uri
        return XLIFF_NS


def main(argv: Optional[list[str]] = None) -> int:
    """CLI interface for mock OL tool."""
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 2:
        print("Usage: mock_ol.py <input.xlf> <output.xlf> [--source-lang en] [--target-lang fr]")
        return 1

    input_path = Path(argv[0])
    output_path = Path(argv[1])

    source_lang = "en"
    target_lang = "fr"

    i = 2
    while i < len(argv):
        if argv[i] == "--source-lang" and i + 1 < len(argv):
            source_lang = argv[i + 1]
            i += 2
        elif argv[i] == "--target-lang" and i + 1 < len(argv):
            target_lang = argv[i + 1]
            i += 2
        else:
            i += 1

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    mock_ol = MockOLTool(source_lang=source_lang, target_lang=target_lang)
    success = mock_ol.translate_xliff(input_path, output_path)

    if success:
        print(f"Translation complete: {output_path}")
        return 0
    else:
        print("Translation failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())