"""T-06 — every OPP MCP tool returns the unified ``{success, content}`` envelope.

Gap-register task T-06: ``extract_document`` and ``batch_extract`` returned
flat payload dicts (``md_content``, ``results``, … at the top level) while
the other seven tools wrapped their payload under ``content``. This test
enumerates all nine tools and asserts each one returns exactly the two
top-level keys ``success`` + ``content``.

Contract under test (cross-repo standard, ``docs/ERROR_CODES.md:15-29``):

    Success: {success: true, content: {dict}}
    Error:   {success: false, error: {code, message}}   (no content)

This module only exercises the success half; the error half is already
covered by ``test_server.py`` and ``test_t07_error_envelope.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opp.mcp import server as opp_server
from opp.mcp.config import MCPConfig

BATCH_TEST_DIR = Path(__file__).resolve().parents[2] / "batch_test"
PHASE0_OFFICE_DIR = BATCH_TEST_DIR / "phase0_office"
DOCX_PATH = str(PHASE0_OFFICE_DIR / "normal.docx")

# A structurally valid XLIFF 1.2 snippet for validate_xliff.
MINIMAL_XLIFF = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 '
    'http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">'
    "<file source-language=\"en\" target-language=\"zh\" datatype=\"plaintext\">"
    "<body><trans-unit id=\"1\"><source>Hello</source></trans-unit></body>"
    "</file></xliff>"
)


@pytest.fixture
def setup_server(tmp_path: Path):
    cfg = MCPConfig(
        allowed_directories=[PHASE0_OFFICE_DIR, tmp_path],
        max_file_size_bytes=100_000_000,
        request_timeout_seconds=60,
        max_images_per_extraction=100,
        max_extraction_depth=3,
        resource_storage_dir=tmp_path / "resources",
    )
    opp_server._init_server(cfg)
    return cfg


# (tool_name, kwargs factory) — one successful invocation per tool.
def _success_cases(tmp_path: Path) -> list[tuple[str, dict]]:
    return [
        ("ping", {}),
        ("detect_format_tool", {"file_path": DOCX_PATH}),
        (
            "extract_document",
            {"file_path": DOCX_PATH, "output_formats": ["md"]},
        ),
        (
            "batch_extract",
            {"file_paths": [DOCX_PATH], "output_formats": ["md"]},
        ),
        (
            "generate_markdown",
            {"file_path": DOCX_PATH, "output_path": str(tmp_path / "out.md")},
        ),
        (
            "generate_xliff",
            {
                "file_path": DOCX_PATH,
                "output_path": str(tmp_path / "out.xlf"),
                "source_lang": "en",
                "target_lang": "zh",
            },
        ),
        (
            "save_skeleton",
            {
                "file_path": DOCX_PATH,
                "base_name": "normal",
                "output_dir": str(tmp_path),
            },
        ),
        ("validate_xliff", {"xliff_content": MINIMAL_XLIFF}),
        ("get_capabilities", {}),
    ]


EXPECTED_TOP_LEVEL = {"success", "content"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
        "ping",
        "detect_format_tool",
        "extract_document",
        "batch_extract",
        "generate_markdown",
        "generate_xliff",
        "save_skeleton",
        "validate_xliff",
        "get_capabilities",
    ],
)
async def test_success_envelope_top_level_keys(setup_server, tmp_path, tool_name):
    """Each of the 9 OPP tools must return exactly {success, content} on success."""
    cases = dict((name, kwargs) for name, kwargs in _success_cases(tmp_path))
    fn = getattr(opp_server, tool_name)
    result = await fn(**cases[tool_name])

    assert result["success"] is True, (
        f"{tool_name}: success must be True, got {result!r}"
    )
    assert set(result.keys()) == EXPECTED_TOP_LEVEL, (
        f"{tool_name}: top-level keys must be exactly {{success, content}}, "
        f"got {sorted(result.keys())}"
    )
    assert isinstance(result["content"], dict), (
        f"{tool_name}: content must be a dict, got {type(result['content'])}"
    )
    assert result["content"], (
        f"{tool_name}: content must carry the tool payload, got empty dict"
    )
