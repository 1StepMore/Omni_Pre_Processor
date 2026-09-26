"""MCP schema↔signature contract for OPP.

The MCP ``inputSchema`` is the surface an agent sees; the dispatched tool
function is what actually runs. Any property advertised in a schema MUST be
accepted by the corresponding function, otherwise a well-behaved caller that
sends the advertised parameter gets ``OPP_INTERNAL_ERROR`` (a ``TypeError``
swallowed by the error boundary) instead of a result.

Regression context: ``extract_document``'s schema advertises ``traceparent``
for W3C Trace Context propagation, but its function signature did not accept
it — the dispatcher reads ``traceparent`` for tracing and then forwards the
whole argument dict to ``fn(**arguments)``, so the extra key raised
``TypeError: extract_document() got an unexpected keyword argument
'traceparent'``. This module locks both the specific fix and the general
schema/signature parity invariant so future drift fails here.
"""

from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest
from opp.mcp import server as opp_server
from opp.mcp.config import MCPConfig

#: Tracked fixture source. The test copies it into ``tmp_path`` and points the
#: dispatcher only at temporary paths so extraction never writes next to the
#: tracked fixture (which previously produced an untracked
#: ``batch_test/phase0_office/normal.skeleton.zip``).
FIXTURE_DOCX = (
    Path(__file__).resolve().parents[2]
    / "batch_test"
    / "phase0_office"
    / "normal.docx"
)

#: A syntactically valid W3C Trace Context ``traceparent``.
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@pytest.fixture
def extracted_docx(tmp_path: Path) -> Path:
    """Copy the tracked fixture into ``tmp_path`` and route all extraction
    output (resources, markdown, images JSON, skeleton) under ``tmp_path``.

    Given the dispatcher only ever receives a temporary input path and a
    temporary ``output_dir``, a run leaves no new files under ``batch_test/``.
    """
    docx_path = tmp_path / "normal.docx"
    shutil.copyfile(FIXTURE_DOCX, docx_path)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    cfg = MCPConfig(
        allowed_directories=[tmp_path],
        max_file_size_bytes=100_000_000,
        request_timeout_seconds=60,
        max_images_per_extraction=100,
        max_extraction_depth=3,
        resource_storage_dir=tmp_path / "resources",
        output_dir=output_dir,
    )
    opp_server._init_server(cfg)
    return docx_path


def test_every_schema_property_is_accepted_by_dispatched_function():
    """Given the registry, When I inspect each schema, Then every advertised
    property is an accepted keyword of the tool function.

    This is the general invariant behind the ``traceparent`` bug: the schema
    must never advertise a parameter the function rejects.
    """
    assert len(opp_server._TOOL_SCHEMAS) == 9, "source truth is nine MCP tools"

    for schema in opp_server._TOOL_SCHEMAS:
        name = schema["name"]
        fn = opp_server._TOOL_DISPATCH[name]
        signature = inspect.signature(fn)
        accepted = set(signature.parameters)
        accepts_var_kwargs = any(
            param.kind is inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )
        advertised = set(schema["inputSchema"].get("properties", {}))

        if accepts_var_kwargs:
            continue

        rejected = advertised - accepted
        assert not rejected, (
            f"{name}: schema advertises parameter(s) {sorted(rejected)} that "
            f"the tool function rejects; accepted={sorted(accepted)}"
        )


@pytest.mark.asyncio
async def test_extract_document_accepts_traceparent_through_dispatch(
    extracted_docx: Path, tmp_path: Path
):
    """Given the schema advertises ``traceparent``, When a client sends it
    through the dispatcher, Then extraction succeeds (not OPP_INTERNAL_ERROR)
    and every produced artifact stays under ``tmp_path``.
    """
    result = await opp_server._handle_call_tool(
        "extract_document",
        {
            "file_path": str(extracted_docx),
            "output_formats": ["md"],
            "traceparent": TRACEPARENT,
        },
    )

    assert len(result) == 1
    parsed = json.loads(result[0].text)

    assert parsed["success"] is True, (
        "extract_document rejected its schema-advertised traceparent "
        f"parameter: {parsed.get('error_code')} / {parsed.get('message')}"
    )
    assert isinstance(parsed.get("content"), dict)

    skeleton_path = parsed["content"].get("skeleton_path")
    assert skeleton_path is not None, (
        "expected the DOCX skeleton to be saved under the configured "
        "temporary output_dir"
    )
    assert Path(skeleton_path).is_relative_to(tmp_path), (
        f"skeleton written outside tmp_path: {skeleton_path}"
    )
