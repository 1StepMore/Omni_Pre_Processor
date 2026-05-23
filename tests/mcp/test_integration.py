"""Integration tests for OPP MCP server logic.

These tests call the server functions directly to verify OPP extraction
and conversion logic works correctly through the MCP interface.
"""

import asyncio
from pathlib import Path

import pytest


BATCH_TEST_DIR = Path(__file__).parent.parent.parent / "batch_test"
PHASE0_OFFICE_DIR = BATCH_TEST_DIR / "phase0_office"
DOCX_PATH = str(PHASE0_OFFICE_DIR / "normal.docx")
PDF_PATH = str(PHASE0_OFFICE_DIR / "normal.pdf")


@pytest.fixture
def mcp_server():
    """Initialize MCP server state."""
    from opp.mcp.config import MCPConfig
    from opp.mcp.server import _init_server

    config = MCPConfig(
        allowed_directories=[PHASE0_OFFICE_DIR.resolve()],
        max_file_size_bytes=100_000_000,
        resource_storage_dir=Path("./mcp_resources"),
    )
    _init_server(config)
    return True


class TestOPPFunctions:
    """Test OPP MCP server functions directly."""

    def test_ping(self, mcp_server):
        """Test ping returns success."""
        from opp.mcp.server import ping

        result = asyncio.run(ping())
        assert result == {"success": True}

    def test_detect_format_docx(self, mcp_server):
        """Test format detection for DOCX."""
        from opp.mcp.server import detect_format_tool

        result = asyncio.run(detect_format_tool(DOCX_PATH))
        assert result["success"] is True
        assert result["format"].upper() == "DOCX"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_detect_format_pdf(self, mcp_server):
        """Test format detection for PDF."""
        from opp.mcp.server import detect_format_tool

        result = asyncio.run(detect_format_tool(PDF_PATH))
        assert result["success"] is True
        assert result["format"].upper() == "PDF"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_extract_document_md(self, mcp_server):
        """Test extract_document with markdown output."""
        from opp.mcp.server import extract_document

        result = asyncio.run(extract_document(
            file_path=DOCX_PATH,
            output_formats=["md"],
        ))
        assert result["success"] is True
        assert "md_content" in result
        assert len(result["md_content"]) > 0

    def test_extract_document_invalid_path(self, mcp_server):
        """Test extract_document with invalid path."""
        from opp.mcp.server import extract_document

        result = asyncio.run(extract_document(
            file_path="/nonexistent/path.docx",
        ))
        assert result["success"] is False
        assert "error" in result

    def test_generate_markdown(self, mcp_server):
        """Test generate_markdown tool."""
        from opp.mcp.server import generate_markdown

        result = asyncio.run(generate_markdown(file_path=DOCX_PATH))
        assert result["success"] is True
        assert "markdown_content" in result
        assert len(result["markdown_content"]) > 0
        assert "output_path" in result

    def test_generate_xliff(self, mcp_server):
        """Test generate_xliff tool."""
        from opp.mcp.server import generate_xliff

        result = asyncio.run(generate_xliff(
            file_path=DOCX_PATH,
            source_lang="en",
            target_lang="zh",
        ))
        assert result["success"] is True
        assert "xliff_content" in result
        assert "units_count" in result
        assert result["units_count"] > 0

    def test_batch_extract(self, mcp_server):
        """Test batch_extract with multiple files."""
        from opp.mcp.server import batch_extract

        result = asyncio.run(batch_extract(
            file_paths=[DOCX_PATH],
            output_formats=["md"],
        ))
        assert result["success"] is True
        assert result["successful"] == 1
        assert result["failed"] == 0
        assert len(result["results"]) == 1

    def test_batch_extract_invalid_file(self, mcp_server):
        """Test batch_extract with one invalid file."""
        from opp.mcp.server import batch_extract

        result = asyncio.run(batch_extract(
            file_paths=["/invalid/docx"],
            output_formats=["md"],
        ))
        assert result["success"] is False
        assert result["failed"] == 1
        assert result["successful"] == 0

    def test_output_formats_string_coercion(self, mcp_server):
        """Test that string output_formats is coerced to list."""
        from opp.mcp.server import extract_document

        result = asyncio.run(extract_document(
            file_path=DOCX_PATH,
            output_formats="md",
        ))
        assert result["success"] is True