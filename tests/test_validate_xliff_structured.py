"""Regression tests for the ``validate_xliff`` parameter alias + structured errors.

Context (reported defect): the PEMT runbook and ORF's ``apply_xliff`` call the
tool as ``validate_xliff(xliff_path=...)`` while the tool only accepted
``file_path``. The unknown keyword raised a ``TypeError`` that the error
boundary swallowed, so a perfectly legal XLIFF came back as
``OPP_INTERNAL_ERROR`` / "report a bug". These tests pin:

- ``xliff_path`` is accepted as a first-class alias for ``file_path``;
- supplying both is rejected as ``OPP_INVALID_INPUT``;
- the dispatcher reports unknown/missing parameters as ``OPP_INVALID_INPUT``
  instead of an opaque ``OPP_INTERNAL_ERROR``;
- ``content.errors`` carries machine-readable codes + line numbers.
"""
from __future__ import annotations

import asyncio
import json

import pytest

# Guard the module this file actually imports (`opp.mcp.server` pulls in the
# whole MCP surface): guarding bare `opp` is vacuous (opp is this repo's own
# package) and turns a missing optional `mcp` extra into a collection ERROR.
pytest.importorskip(
    "opp.mcp.server",
    reason="opp.mcp server not available (needs the optional 'mcp' extra)",
)

from opp.mcp import server as opp_server  # noqa: E402
from opp.mcp.config import MCPConfig  # noqa: E402
from opp.mcp.tools.validate_xliff import validate_xliff  # noqa: E402


VALID_XLIFF = """<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test.md" source-language="en" target-language="zh" datatype="plaintext">
    <body>
      <trans-unit id="tu-1">
        <source>Hello world</source>
        <target>你好世界</target>
      </trans-unit>
      <trans-unit id="tu-2">
        <source>Goodbye</source>
        <target>再见</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""

# `<source>` never closed -> XMLSyntaxError.
MALFORMED_UNTERMINATED_SOURCE = (
    '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
    '<file original="a" source-language="en"><body><trans-unit id="1">'
    "<source>Hello</target></trans-unit></body></file></xliff>"
)

DUPLICATE_ID_XLIFF = (
    '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
    '<file original="a" source-language="en" target-language="zh"><body>'
    '<trans-unit id="7"><source>A</source><target>B</target></trans-unit>'
    '<trans-unit id="7"><source>C</source><target>D</target></trans-unit>'
    "</body></file></xliff>"
)

MISSING_SOURCE_XLIFF = (
    '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
    '<file original="a" source-language="en" target-language="zh"><body>'
    '<trans-unit id="3"><target>B</target></trans-unit>'
    "</body></file></xliff>"
)

MISSING_SOURCE_LANGUAGE_XLIFF = (
    '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
    '<file original="a"><body><trans-unit id="1"><source>A</source>'
    "</trans-unit></body></file></xliff>"
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def allowed_tmp(tmp_path):
    """Initialize the MCP server so ``tmp_path`` is an allowed directory."""
    cfg = MCPConfig(
        allowed_directories=[tmp_path],
        max_file_size_bytes=100_000_000,
        request_timeout_seconds=60,
        max_images_per_extraction=100,
        max_extraction_depth=3,
        resource_storage_dir=tmp_path / "resources",
    )
    opp_server._init_server(cfg)
    return tmp_path


@pytest.fixture
def valid_xliff_file(allowed_tmp):
    path = allowed_tmp / "valid.xlf"
    path.write_text(VALID_XLIFF, encoding="utf-8")
    return path


# ── parameter alias: file_path / xliff_path ──────────────────────────


def test_legal_xliff_via_file_path(valid_xliff_file):
    result = _run(validate_xliff(file_path=str(valid_xliff_file)))
    assert result["success"] is True
    assert result["content"]["is_valid"] is True
    assert result["content"]["errors"] == []


def test_legal_xliff_via_xliff_path(valid_xliff_file):
    """The reported symptom: the pipeline's `xliff_path` must work."""
    result = _run(validate_xliff(xliff_path=str(valid_xliff_file)))
    assert result["success"] is True
    assert result["content"]["is_valid"] is True
    assert result["content"]["errors"] == []


def test_file_path_and_xliff_path_are_equivalent(valid_xliff_file):
    by_file = _run(validate_xliff(file_path=str(valid_xliff_file)))
    by_alias = _run(validate_xliff(xliff_path=str(valid_xliff_file)))
    assert by_file == by_alias


def test_both_paths_rejected(valid_xliff_file):
    result = _run(
        validate_xliff(file_path=str(valid_xliff_file), xliff_path=str(valid_xliff_file))
    )
    assert result["success"] is False
    assert result["error_code"] == "OPP_INVALID_INPUT"
    assert result["error"]["message"] == "Provide only one of file_path / xliff_path."


# ── dispatcher guard: unknown / missing parameters ───────────────────


def test_dispatcher_unknown_parameter_names_it():
    """An unknown parameter must not become OPP_INTERNAL_ERROR."""
    raw = _run(
        opp_server._handle_call_tool("validate_xliff", {"bogus_param": "x"})
    )
    payload = json.loads(raw[0].text)
    assert payload["success"] is False
    assert payload["error_code"] == "OPP_INVALID_INPUT"
    assert "bogus_param" in payload["error"]["message"]
    assert "recovery" in payload


def test_dispatcher_missing_required_parameter():
    raw = _run(opp_server._handle_call_tool("extract_document", {}))
    payload = json.loads(raw[0].text)
    assert payload["success"] is False
    assert payload["error_code"] == "OPP_INVALID_INPUT"
    assert "file_path" in payload["error"]["message"]
    assert "Missing required parameter" in payload["error"]["message"]


def test_dispatcher_internal_type_error_still_reports_internal():
    """A TypeError raised *inside* a tool is a real bug, not bad input.

    ``validate_xliff`` is dispatched with a valid signature but an object whose
    ``encode`` raises TypeError, proving the dispatcher binding guard only
    checks the signature and does not remap runtime TypeErrors.
    """

    class Boom(str):
        def encode(self, *args, **kwargs):  # noqa: D102
            raise TypeError("boom from inside the tool")

    raw = _run(
        opp_server._handle_call_tool("validate_xliff", {"xliff_content": Boom("x")})
    )
    payload = json.loads(raw[0].text)
    assert payload["success"] is False
    assert payload["error_code"] == "OPP_INTERNAL_ERROR"


# ── structured error codes ───────────────────────────────────────────


def test_malformed_xml_reports_code_and_line():
    result = _run(validate_xliff(xliff_content=MALFORMED_UNTERMINATED_SOURCE))
    assert result["success"] is True
    content = result["content"]
    assert content["is_valid"] is False
    assert content["errors"][0]["code"] == "MALFORMED_XML"
    assert content["errors"][0]["line"] is not None


def test_duplicate_id_reports_duplicate_code():
    result = _run(validate_xliff(xliff_content=DUPLICATE_ID_XLIFF))
    content = result["content"]
    assert content["is_valid"] is False
    dup = [e for e in content["errors"] if e["code"] == "DUPLICATE_ID"]
    assert dup, content["errors"]
    assert "7" in dup[0]["message"]


def test_missing_source_reports_missing_source_code():
    result = _run(validate_xliff(xliff_content=MISSING_SOURCE_XLIFF))
    content = result["content"]
    assert content["is_valid"] is False
    missing = [e for e in content["errors"] if e["code"] == "MISSING_SOURCE"]
    assert missing, content["errors"]
    assert "3" in missing[0]["message"]


def test_schema_error_reports_code_and_line():
    result = _run(validate_xliff(xliff_content=MISSING_SOURCE_LANGUAGE_XLIFF))
    content = result["content"]
    assert content["is_valid"] is False
    schema_errors = [e for e in content["errors"] if e["code"] == "SCHEMA_ERROR"]
    assert schema_errors, content["errors"]
    assert schema_errors[0]["line"] is not None


def test_legal_xliff_has_no_structured_errors(valid_xliff_file):
    result = _run(validate_xliff(xliff_path=str(valid_xliff_file)))
    assert result["content"]["errors"] == []
    assert result["content"]["error_count"] == 0
