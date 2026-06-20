"""KeyValueChannel - converts flat dict to XLIFF 1.2 trans-unit elements."""


from translate.storage.xliff import xlifffile


class KeyValueChannel:
    """Converts flat key-value dictionary to XLIFF 1.2 XML string.

    Each key-value pair becomes a <trans-unit> element where:
    - key becomes the trans-unit id attribute
    - value becomes the <source> element text
    - full key path is preserved in a <note> element for context

    Example:
        Input:  {"ui.menu.save": "Save", "ui.menu.exit": "Exit"}
        Output: XLIFF 1.2 XML with two trans-unit elements
    """

    def __init__(self, skip_empty: bool = True) -> None:
        """Initialize the KeyValueChannel.

        Args:
            skip_empty: If True (default), skip null and empty string values.
                        If False, include all values.
        """
        self._skip_empty = skip_empty

    def convert(self, data: dict[str, str]) -> str:
        """Convert a dictionary of key-value pairs to XLIFF 1.2 XML string.

        Args:
            data: Dictionary where keys are dot-notation paths (e.g., "ui.menu.save")
                  and values are the source text to translate.

        Returns:
            XLIFF 1.2 compliant XML string

        Raises:
            ValueError: If data is None
        """
        if data is None:
            raise ValueError("data cannot be None")

        store = xlifffile()

        for key, value in data.items():
            # Skip null/empty values if configured to do so
            if self._skip_empty and (value is None or value == ""):
                continue

            # Create trans-unit with key as id and value as source
            unit = store.addsourceunit(str(value))
            if unit is not None:
                unit.setid(str(key))
                unit.addnote(f"Context: {key}", origin="KeyValueChannel")
                # Preserve whitespace on <source> element
                ns_uri = "urn:oasis:names:tc:xliff:document:1.1"
                xml_space_attr = "{http://www.w3.org/XML/1998/namespace}space"
                source_elem = unit.xmlelement.find(f"{{{ns_uri}}}source")
                if source_elem is None:
                    source_elem = unit.xmlelement.find("source")
                if source_elem is not None:
                    source_elem.set(xml_space_attr, "preserve")

        # Return XLIFF 1.2 XML string
        return bytes(store).decode("utf-8")

    def convert_to_file(self, data: dict[str, str], path: str | None = None) -> bytes:
        """Convert data and optionally write to a file.

        Args:
            data: Dictionary of key-value pairs
            path: Optional file path to write the XLIFF content to

        Returns:
            XLIFF content as bytes
        """
        content = self.convert(data)
        result = content.encode("utf-8")

        if path:
            with open(path, "wb") as f:
                f.write(result)

        return result