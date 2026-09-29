"""XLIFF file validator for translation workflows."""

from lxml import etree

from opp.xliff.xliff_dataclasses import _VALID_LANGUAGE_CODES

# XLIFF 1.2 namespace (OASIS standard, what XLIFFFileGenerator emits)
XLIFF_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_NS = {"xlf": XLIFF_NAMESPACE}

# Minimal XLIFF 1.2 XSD schema (bundled locally - no network calls)
# Based on OASIS XLIFF 1.2 specification
_XLIFF_1_2_XSD = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xlf="urn:oasis:names:tc:xliff:document:1.2"
            xmlns:xml="http://www.w3.org/XML/1998/namespace"
            targetNamespace="urn:oasis:names:tc:xliff:document:1.2"
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


# XML namespace for the reserved xml:space attribute.
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_XML_SPACE_ATTR = "{" + _XML_NAMESPACE + "}space"


class XLIFFValidator:
    """Validator for XLIFF 1.2 files.

    Validates XLIFF files against:
    - OASIS XLIFF 1.2 XSD schema
    - Trans-unit content rules (non-empty source, unique IDs, valid language codes)
    """

    def __init__(self) -> None:
        """Initialize the validator with XLIFF 1.2 XSD schema."""
        self._schema = etree.XMLSchema(etree.fromstring(_XLIFF_1_2_XSD))

    # ── shared parsing helpers ──────────────────────────────────────

    @staticmethod
    def _parse(xliff_bytes: bytes) -> tuple[etree._Element | None, etree.XMLSyntaxError | None]:
        """Parse *xliff_bytes* once; return (doc, syntax_error)."""
        try:
            doc = etree.fromstring(xliff_bytes)
        except etree.XMLSyntaxError as exc:
            return None, exc
        return doc, None

    @staticmethod
    def _strip_xml_space_attrs(doc: etree._Element) -> None:
        """Remove reserved ``xml:space`` attributes before XSD validation."""
        for elem in doc.iter():
            if _XML_SPACE_ATTR in elem.attrib:
                del elem.attrib[_XML_SPACE_ATTR]

    @staticmethod
    def _line_of(elem: etree._Element) -> int | None:
        """Best-effort source line for *elem* (None when unavailable)."""
        line = getattr(elem, "sourceline", None)
        return line if isinstance(line, int) else None

    def _validate_schema_doc(
        self, doc: etree._Element
    ) -> tuple[bool, list[str], list[dict[str, object]]]:
        """Schema-validate a parsed doc.

        Returns ``(is_valid, legacy_messages, structured_errors)``.
        """
        if self._schema.validate(doc):
            return True, [], []
        legacy: list[str] = []
        structured: list[dict[str, object]] = []
        for error in self._schema.error_log:
            legacy.append(f"Schema validation error: {error.message}")
            structured.append(
                {
                    "code": "SCHEMA_ERROR",
                    "message": error.message,
                    "line": error.line,
                    "column": error.column,
                }
            )
        return False, legacy, structured

    def _validate_trans_units_doc(
        self, doc: etree._Element
    ) -> tuple[bool, list[str], list[str], list[dict[str, object]]]:
        """Validate trans-unit rules on a parsed doc.

        Returns ``(is_valid, warnings, legacy_errors, structured_errors)``.
        """
        warnings: list[str] = []
        errors: list[str] = []
        structured: list[dict[str, object]] = []

        # Get all trans-unit elements (including nested ones)
        trans_units = doc.xpath("//xlf:trans-unit", namespaces=XLIFF_NS)

        if not trans_units:
            warnings.append("No trans-unit elements found in XLIFF file")

        # Track unique IDs
        seen_ids: set[str] = set()

        for idx, unit in enumerate(trans_units):
            unit_id = unit.get("id", "")
            line = self._line_of(unit)

            # Check for empty ID
            if not unit_id:
                errors.append(f"trans-unit at index {idx} has empty id attribute")
                structured.append(
                    {
                        "code": "EMPTY_ID",
                        "message": f"trans-unit at index {idx} has empty id attribute",
                        "line": line,
                        "column": None,
                    }
                )
                continue

            # Check for duplicate IDs
            if unit_id in seen_ids:
                errors.append(f"Duplicate trans-unit id: '{unit_id}'")
                structured.append(
                    {
                        "code": "DUPLICATE_ID",
                        "message": f"Duplicate trans-unit id: '{unit_id}'",
                        "line": line,
                        "column": None,
                    }
                )
            seen_ids.add(unit_id)

            # Check source element exists and is non-empty
            source_el = unit.find("xlf:source", namespaces=XLIFF_NS)
            if source_el is None:
                errors.append(f"trans-unit id='{unit_id}': missing <source> element")
                structured.append(
                    {
                        "code": "MISSING_SOURCE",
                        "message": f"trans-unit id='{unit_id}': missing <source> element",
                        "line": line,
                        "column": None,
                    }
                )
            else:
                source_text = "".join(source_el.itertext()).strip()
                if not source_text:
                    errors.append(f"trans-unit id='{unit_id}': <source> element is empty")
                    structured.append(
                        {
                            "code": "EMPTY_SOURCE",
                            "message": f"trans-unit id='{unit_id}': <source> element is empty",
                            "line": self._line_of(source_el) or line,
                            "column": None,
                        }
                    )

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
        return is_valid, warnings, errors, structured

    # ── public API ──────────────────────────────────────────────────

    def validate_schema(self, xliff_bytes: bytes) -> tuple[bool, list[str]]:
        """Validate XLIFF bytes against OASIS XLIFF 1.2 XSD schema.

        Args:
            xliff_bytes: Raw bytes of the XLIFF file

        Returns:
            Tuple of (is_valid, error_messages)
            - is_valid: True if schema is valid
            - error_messages: List of error strings (empty if valid)
        """
        doc, syntax_error = self._parse(xliff_bytes)
        if syntax_error is not None:
            return False, [f"Malformed XML: {syntax_error}"]
        assert doc is not None
        self._strip_xml_space_attrs(doc)
        is_valid, legacy, _structured = self._validate_schema_doc(doc)
        return is_valid, legacy

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
        doc, syntax_error = self._parse(xliff_bytes)
        if syntax_error is not None:
            return False, [], [f"Malformed XML: {syntax_error}"]
        assert doc is not None
        is_valid, warnings, errors, _structured = self._validate_trans_units_doc(doc)
        return is_valid, warnings, errors

    def validate(self, xliff_bytes: bytes) -> dict:
        """Return a fully structured validation envelope.

        Runs schema + trans-unit validation on a single parse so the two
        paths cannot drift. Alongside the legacy ``schema_errors`` /
        ``trans_unit_errors`` string lists (kept verbatim for back-compat),
        it returns an ``errors`` list of machine-readable entries with a
        stable ``code`` and best-effort ``line``/``column`` location.

        Codes: ``MALFORMED_XML``, ``SCHEMA_ERROR``, ``EMPTY_ID``,
        ``DUPLICATE_ID``, ``MISSING_SOURCE``, ``EMPTY_SOURCE``.
        """
        doc, syntax_error = self._parse(xliff_bytes)
        if syntax_error is not None:
            malformed = f"Malformed XML: {syntax_error}"
            line, column = syntax_error.position
            errors = [
                {
                    "code": "MALFORMED_XML",
                    "message": malformed,
                    "line": line,
                    "column": column,
                }
            ]
            return {
                "is_valid": False,
                "schema_valid": False,
                "trans_units_valid": False,
                "schema_errors": [malformed],
                "trans_unit_errors": [malformed],
                "trans_unit_warnings": [],
                "errors": errors,
                "error_count": len(errors),
                "warning_count": 0,
            }

        assert doc is not None
        self._strip_xml_space_attrs(doc)
        schema_valid, schema_errors, schema_structured = self._validate_schema_doc(doc)
        tu_valid, tu_warnings, tu_errors, tu_structured = (
            self._validate_trans_units_doc(doc)
        )

        errors = schema_structured + tu_structured
        warnings = list(tu_warnings)
        return {
            "is_valid": bool(schema_valid) and bool(tu_valid),
            "schema_valid": bool(schema_valid),
            "trans_units_valid": bool(tu_valid),
            "schema_errors": list(schema_errors),
            "trans_unit_errors": list(tu_errors),
            "trans_unit_warnings": warnings,
            "errors": errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
