"""Regression tests for the OPP MCP server.py → tools/ package split.

Verifies that all 7 tool functions and ``_init_server`` remain importable
from ``opp.mcp.server`` (backward compat) and from ``opp.mcp.tools``
(new canonical location).
"""

import asyncio
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────
# Backward-compat imports from opp.mcp.server
# ─────────────────────────────────────────────────────────────────────

class TestServerReExports:
    """Verify all symbols are re-exported from opp.mcp.server."""

    def test_init_server_importable(self):
        from opp.mcp.server import _init_server
        assert callable(_init_server)

    def test_ping_importable(self):
        from opp.mcp.server import ping
        assert callable(ping)

    def test_detect_format_tool_importable(self):
        from opp.mcp.server import detect_format_tool
        assert callable(detect_format_tool)

    def test_save_skeleton_importable(self):
        from opp.mcp.server import save_skeleton
        assert callable(save_skeleton)

    def test_generate_markdown_importable(self):
        from opp.mcp.server import generate_markdown
        assert callable(generate_markdown)

    def test_generate_xliff_importable(self):
        from opp.mcp.server import generate_xliff
        assert callable(generate_xliff)

    def test_extract_document_importable(self):
        from opp.mcp.server import extract_document
        assert callable(extract_document)

    def test_batch_extract_importable(self):
        from opp.mcp.server import batch_extract
        assert callable(batch_extract)

    def test_all_seven_in_server(self):
        """Verify all 7 tool names are present in opp.mcp.server."""
        import opp.mcp.server as srv
        tool_names = {
            "ping",
            "detect_format_tool",
            "save_skeleton",
            "generate_markdown",
            "generate_xliff",
            "extract_document",
            "batch_extract",
        }
        for name in tool_names:
            assert hasattr(srv, name), f"opp.mcp.server missing {name}"


# ─────────────────────────────────────────────────────────────────────
# New canonical imports from opp.mcp.tools
# ─────────────────────────────────────────────────────────────────────

class TestToolsPackage:
    """Verify all tool functions are importable from opp.mcp.tools."""

    def test_ping_importable(self):
        from opp.mcp.tools import ping
        assert callable(ping)

    def test_detect_format_tool_importable(self):
        from opp.mcp.tools import detect_format_tool
        assert callable(detect_format_tool)

    def test_save_skeleton_importable(self):
        from opp.mcp.tools import save_skeleton
        assert callable(save_skeleton)

    def test_generate_markdown_importable(self):
        from opp.mcp.tools import generate_markdown
        assert callable(generate_markdown)

    def test_generate_xliff_importable(self):
        from opp.mcp.tools import generate_xliff
        assert callable(generate_xliff)

    def test_extract_document_importable(self):
        from opp.mcp.tools import extract_document
        assert callable(extract_document)

    def test_batch_extract_importable(self):
        from opp.mcp.tools import batch_extract
        assert callable(batch_extract)

    def test_all_seven_in_tools(self):
        """Verify all 7 tool names are present in opp.mcp.tools."""
        import opp.mcp.tools as tools
        tool_names = {
            "ping",
            "detect_format_tool",
            "save_skeleton",
            "generate_markdown",
            "generate_xliff",
            "extract_document",
            "batch_extract",
        }
        for name in tool_names:
            assert hasattr(tools, name), f"opp.mcp.tools missing {name}"


# ─────────────────────────────────────────────────────────────────────
# Common module tests
# ─────────────────────────────────────────────────────────────────────

class TestCommonModule:
    """Verify shared helpers and state are accessible."""

    def test_common_importable(self):
        from opp.mcp import common
        assert hasattr(common, "_init_server")
        assert hasattr(common, "_suggest_pipeline")
        assert hasattr(common, "_safe_unlink")
        assert hasattr(common, "_safe_temp_output")
        assert hasattr(common, "_config")
        assert hasattr(common, "_validator")

    def test_suggest_pipeline(self):
        from opp.mcp.common import _suggest_pipeline
        assert _suggest_pipeline("pdf") == "md_only"
        assert _suggest_pipeline("docx") == "both"
        assert _suggest_pipeline("pptx") == "both"
        assert _suggest_pipeline("unknown") == "neither"
        assert _suggest_pipeline("html") == "md_only"
        assert _suggest_pipeline("") == "md_only"


# ─────────────────────────────────────────────────────────────────────
# Function identity: imported from server vs tools should be the same
# ─────────────────────────────────────────────────────────────────────

class TestFunctionIdentity:
    """Tool functions imported from server vs tools must be identical."""

    def _check_identical(self, name: str):
        server_mod = __import__("opp.mcp.server", fromlist=[name])
        tools_mod = __import__("opp.mcp.tools", fromlist=[name])
        server_fn = getattr(server_mod, name)
        tools_fn = getattr(tools_mod, name)
        assert server_fn is tools_fn, (
            f"{name} from server ({id(server_fn)}) != from tools ({id(tools_fn)})"
        )

    def test_ping_identical(self):
        self._check_identical("ping")

    def test_detect_format_tool_identical(self):
        self._check_identical("detect_format_tool")

    def test_save_skeleton_identical(self):
        self._check_identical("save_skeleton")

    def test_generate_markdown_identical(self):
        self._check_identical("generate_markdown")

    def test_generate_xliff_identical(self):
        self._check_identical("generate_xliff")

    def test_extract_document_identical(self):
        self._check_identical("extract_document")

    def test_batch_extract_identical(self):
        self._check_identical("batch_extract")
