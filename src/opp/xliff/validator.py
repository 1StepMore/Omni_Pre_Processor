"""XLIFF file validator for translation workflows."""

from lxml import etree

from opp.xliff.xliff_dataclasses import _VALID_LANGUAGE_CODES

# XLIFF 1.1 namespace (translate-toolkit default)
XLIFF_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.1"
XLIFF_NS = {"xlf": XLIFF_NAMESPACE}

# Minimal XLIFF 1.2 XSD schema (bundled locally - no network calls)
# Based on OASIS XLIFF 1.2 specification
_XLIFF_1_2_XSD = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xlf="urn:oasis:names:tc:xliff:document:1.1"
            xmlns:xml="http://www.w3.org/XML/1998/namespace"
            targetNamespace="urn:oasis:names:tc:xliff:document:1.1"
            elementFormDefault="qualified"
            version="1.2">

  <xsd:import namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="http://www.w3.org/XML/1998/namespace"/>

  <xsd:element name="xliff">
    <xsd:complexType>
      <xsd:sequence>
        <xsd:element ref="xlf:file" minOccurs="1" maxOccurs="unbounded"/>
      </xsd:sequence>
      <xsd:attribute name="version" type="xsd:string" use="required"/>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="file">
    <xsd:complexType>
      <xsd:sequence>
        <xsd:element ref="xlf:body" minOccurs="1" maxOccurs="1"/>
      </xsd:sequence>
      <xsd:attribute name="original" type="xsd:string" use="optional"/>
      <xsd:attribute name="source-language" type="xsd:string" use="required"/>
      <xsd:attribute name="target-language" type="xsd:string" use="optional"/>
      <xsd:attribute name="datatype" type="xsd:string" use="optional"/>
      <xsd:attribute name="tool-id" type="xsd:string" use="optional"/>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="body">
    <xsd:complexType>
      <xsd:choice>
        <xsd:element ref="xlf:trans-unit" minOccurs="0" maxOccurs="unbounded"/>
        <xsd:element ref="xlf:group" minOccurs="0" maxOccurs="unbounded"/>
      </xsd:choice>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="trans-unit">
    <xsd:complexType>
      <xsd:sequence>
        <xsd:element ref="xlf:source" minOccurs="1" maxOccurs="1"/>
        <xsd:element ref="xlf:target" minOccurs="0" maxOccurs="1"/>
        <xsd:element ref="xlf:note" minOccurs="0" maxOccurs="unbounded"/>
      </xsd:sequence>
      <xsd:attribute name="id" type="xsd:string" use="required"/>
      <xsd:attribute name="resname" type="xsd:string" use="optional"/>
      <xsd:attribute name="restype" type="xsd:string" use="optional"/>
      <xsd:attribute name="translate" type="xsd:string" use="optional"/>
      <xsd:attribute name="approved" type="xsd:string" use="optional"/>
      <xsd:anyAttribute namespace="##any"/>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="source">
    <xsd:complexType mixed="true">
      <xsd:sequence>
        <xsd:any namespace="##other" processContents="lax" minOccurs="0" maxOccurs="unbounded"/>
      </xsd:sequence>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="target">
    <xsd:complexType mixed="true">
      <xsd:sequence>
        <xsd:any namespace="##other" processContents="lax" minOccurs="0" maxOccurs="unbounded"/>
      </xsd:sequence>
    </xsd:complexType>
  </xsd:element>

  <xsd:element name="note" type="xsd:string"/>

  <xsd:element name="group">
    <xsd:complexType>
      <xsd:sequence>
        <xsd:element ref="xlf:trans-unit" minOccurs="0" maxOccurs="unbounded"/>
        <xsd:element ref="xlf:group" minOccurs="0" maxOccurs="unbounded"/>
      </xsd:sequence>
      <xsd:attribute name="id" type="xsd:string" use="optional"/>
      <xsd:attribute name="resname" type="xsd:string" use="optional"/>
    </xsd:complexType>
  </xsd:element>

</xsd:schema>
"""


class XLIFFValidator:
    """Validator for XLIFF 1.2 files.

    Validates XLIFF files against:
    - OASIS XLIFF 1.2 XSD schema
    - Trans-unit content rules (non-empty source, unique IDs, valid language codes)
    """

    def __init__(self) -> None:
        """Initialize the validator with XLIFF 1.2 XSD schema."""
        self._schema = etree.XMLSchema(etree.fromstring(_XLIFF_1_2_XSD))

    def validate_schema(self, xliff_bytes: bytes) -> tuple[bool, list[str]]:
        """Validate XLIFF bytes against OASIS XLIFF 1.2 XSD schema.

        Args:
            xliff_bytes: Raw bytes of the XLIFF file

        Returns:
            Tuple of (is_valid, error_messages)
            - is_valid: True if schema is valid
            - error_messages: List of error strings (empty if valid)
        """
        errors: list[str] = []

        # Try to parse as XML first
        try:
            doc = etree.fromstring(xliff_bytes)
        except etree.XMLSyntaxError as e:
            return False, [f"Malformed XML: {e}"]

        XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
        xml_space_attr = "{" + XML_NAMESPACE + "}space"
        for elem in doc.iter():
            if xml_space_attr in elem.attrib:
                del elem.attrib[xml_space_attr]

        # Validate against schema
        if self._schema.validate(doc):
            return True, []
        else:
            for error in self._schema.error_log:
                errors.append(f"Schema validation error: {error.message}")
            return False, errors

    def validate_trans_units(
        self, xliff_bytes: bytes
    ) -> tuple[bool, list[str], list[str]]:
        """Validate trans-unit elements for content rules.

        Checks:
        - Each trans-unit has non-empty <source>
        - All trans-unit IDs are unique
        - Language codes are valid ISO 639-1

        Args:
            xliff_bytes: Raw bytes of the XLIFF file

        Returns:
            Tuple of (is_valid, warnings, errors)
            - is_valid: True if all checks pass
            - warnings: List of warning strings (e.g., missing target)
            - errors: List of error strings (validation failures)
        """
        warnings: list[str] = []
        errors: list[str] = []

        # Parse XML
        try:
            doc = etree.fromstring(xliff_bytes)
        except etree.XMLSyntaxError as e:
            errors.append(f"Malformed XML: {e}")
            return False, warnings, errors

        # Get all trans-unit elements (including nested ones)
        trans_units = doc.xpath(
            "//xlf:trans-unit", namespaces=XLIFF_NS
        )

        if not trans_units:
            warnings.append("No trans-unit elements found in XLIFF file")

        # Track unique IDs
        seen_ids: set[str] = set()

        for idx, unit in enumerate(trans_units):
            unit_id = unit.get("id", "")

            # Check for empty ID
            if not unit_id:
                errors.append(f"trans-unit at index {idx} has empty id attribute")
                continue

            # Check for duplicate IDs
            if unit_id in seen_ids:
                errors.append(f"Duplicate trans-unit id: '{unit_id}'")
            seen_ids.add(unit_id)

            # Check source element exists and is non-empty
            source_el = unit.find("xlf:source", namespaces=XLIFF_NS)
            if source_el is None:
                errors.append(f"trans-unit id='{unit_id}': missing <source> element")
            else:
                source_text = "".join(source_el.itertext()).strip()
                if not source_text:
                    errors.append(f"trans-unit id='{unit_id}': <source> element is empty")

            # Check target element (warning only if missing, not error)
            target_el = unit.find("xlf:target", namespaces=XLIFF_NS)
            if target_el is None:
                warnings.append(f"trans-unit id='{unit_id}': missing <target> element")

        # Validate file-level language codes
        files = doc.xpath("//xlf:file", namespaces=XLIFF_NS)
        for file_el in files:
            source_lang = file_el.get("source-language", "")
            target_lang = file_el.get("target-language", "")

            if source_lang and source_lang not in _VALID_LANGUAGE_CODES:
                warnings.append(
                    f"file: source-language '{source_lang}' is not a recognized ISO 639-1 code"
                )
            if target_lang and target_lang not in _VALID_LANGUAGE_CODES:
                warnings.append(
                    f"file: target-language '{target_lang}' is not a recognized ISO 639-1 code"
                )

        is_valid = len(errors) == 0
        return is_valid, warnings, errors
