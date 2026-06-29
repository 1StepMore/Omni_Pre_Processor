"""Security regression tests for OPP MCP server (M-1: Unified Path Validation).

These tests verify that OPP's MCP surface enforces path security:
- Path traversal rejection
- System directory protection
- Blocked extension rejection
- Directory containment
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_OPP_SRC = _REPO_ROOT / "src"
if str(_OPP_SRC) not in sys.path:
    sys.path.insert(0, str(_OPP_SRC))


@pytest.fixture
def mcp_server(tmp_path):
    from opp.mcp.config import MCPConfig
    from opp.mcp.server import _init_server

    config = MCPConfig(
        allowed_directories=[tmp_path.resolve()],
        max_file_size_bytes=100_000_000,
        resource_storage_dir=tmp_path / "mcp_resources",
    )
    _init_server(config)
    return tmp_path


class TestOPPPathTraversal:
    def test_extract_document_rejects_traversal(self, mcp_server, tmp_path):
        from opp.mcp.server import extract_document

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        result = asyncio.run(extract_document(
            file_path=traversal_path,
            output_formats=["md"],
        ))
        assert result["success"] is False
        assert "error" in result

    def test_detect_format_rejects_traversal(self, mcp_server, tmp_path):
        from opp.mcp.server import detect_format_tool

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        result = asyncio.run(detect_format_tool(traversal_path))
        assert result["success"] is False
        assert "error" in result

    def test_generate_xliff_rejects_traversal_input(self, mcp_server, tmp_path):
        from opp.mcp.server import generate_xliff

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        result = asyncio.run(generate_xliff(
            file_path=traversal_path,
        ))
        assert result["success"] is False
        assert "error" in result

    def test_generate_markdown_rejects_traversal_input(self, mcp_server, tmp_path):
        from opp.mcp.server import generate_markdown

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        result = asyncio.run(generate_markdown(
            file_path=traversal_path,
        ))
        assert result["success"] is False
        assert "error" in result

    def test_batch_extract_rejects_traversal(self, mcp_server, tmp_path):
        from mcp.shared.exceptions import McpError
        from opp.mcp.server import batch_extract

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        with pytest.raises(McpError) as exc_info:
            asyncio.run(batch_extract(
                file_paths=[traversal_path],
            ))
        assert "PATH" in str(exc_info.value).upper()

    def test_save_skeleton_rejects_traversal(self, mcp_server, tmp_path):
        from opp.mcp.server import save_skeleton

        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        result = asyncio.run(save_skeleton(
            file_path=traversal_path,
        ))
        assert result["success"] is False
        assert "error" in result


class TestOPPOutputPathValidation:
    def test_generate_xliff_rejects_dangerous_output_path(self, mcp_server, tmp_path):
        from opp.mcp.server import generate_xliff

        safe_input = tmp_path / "test.docx"
        safe_input.write_bytes(b"fake-docx")

        dangerous_output = str(tmp_path / ".." / "tmp" / "malicious.xlf")
        result = asyncio.run(generate_xliff(
            file_path=str(safe_input),
            output_path=dangerous_output,
        ))
        assert result["success"] is False

    def test_generate_markdown_rejects_dangerous_output_path(self, mcp_server, tmp_path):
        from opp.mcp.server import generate_markdown

        safe_input = tmp_path / "test.docx"
        safe_input.write_bytes(b"fake-docx")

        dangerous_output = str(tmp_path / ".." / "tmp" / "malicious.md")
        result = asyncio.run(generate_markdown(
            file_path=str(safe_input),
            output_path=dangerous_output,
        ))
        assert result["success"] is False


class TestOPPBlockedExtensions:
    def test_extract_document_rejects_exe(self, mcp_server, tmp_path):
        from opp.mcp.server import extract_document

        exe_path = tmp_path / "malicious.exe"
        exe_path.write_bytes(b"MZ\x00\x00")

        result = asyncio.run(extract_document(
            file_path=str(exe_path),
            output_formats=["md"],
        ))
        assert result["success"] is False

    def test_extract_document_rejects_sh(self, mcp_server, tmp_path):
        from opp.mcp.server import extract_document

        sh_path = tmp_path / "script.sh"
        sh_path.write_text("#!/bin/bash\necho hacked")

        result = asyncio.run(extract_document(
            file_path=str(sh_path),
            output_formats=["md"],
        ))
        assert result["success"] is False


class TestOPPDirectoryContainment:
    def test_extract_document_rejects_path_outside_allowed(self, mcp_server, tmp_path):
        from opp.mcp.server import extract_document

        outside = tmp_path / "outside"
        outside.mkdir()
        file_outside = outside / "test.docx"
        file_outside.write_bytes(b"fake-docx")

        os.environ["OPP_MCP_ALLOWED_DIRS"] = str(tmp_path / "allowed_only")
        (tmp_path / "allowed_only").mkdir()

        from opp.mcp.config import MCPConfig
        from opp.mcp.server import _init_server
        config = MCPConfig(
            allowed_directories=[tmp_path / "allowed_only"],
            max_file_size_bytes=100_000_000,
        )
        _init_server(config)

        result = asyncio.run(extract_document(
            file_path=str(file_outside),
            output_formats=["md"],
        ))
        assert result["success"] is False


class TestOPPSymlinkProtection:
    def test_extract_document_rejects_symlink_outside(self, mcp_server, tmp_path):
        from opp.mcp.server import extract_document

        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.docx"
        secret.write_bytes(b"fake-docx")

        symlink = tmp_path / "link.docx"
        symlink.symlink_to(secret)

        from opp.mcp.config import MCPConfig
        from opp.mcp.server import _init_server
        narrow_dir = tmp_path / "narrow"
        narrow_dir.mkdir()
        config = MCPConfig(
            allowed_directories=[narrow_dir.resolve()],
            max_file_size_bytes=100_000_000,
        )
        _init_server(config)

        result = asyncio.run(extract_document(
            file_path=str(symlink),
            output_formats=["md"],
        ))
        assert result["success"] is False
