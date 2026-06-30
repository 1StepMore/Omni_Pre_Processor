"""get_capabilities tool for OPP.

Returns module-level static information about what the OPP MCP server
can do. This is the "self-description" feature requested by agents.
"""
from __future__ import annotations

import json
from typing import Optional

from opp.mcp._errors import McpError, mcp_error_boundary
from opp.mcp.auth import check_auth
from opp.mcp.rate_limiter import check_rate_limit


# 16 input formats (must match opp/extractors/__init__.py)
_INPUT_FORMATS = [
    "docx", "pptx", "pdf", "xlsx", "csv", "json", "xml", "html",
    "epub", "eml", "msg", "image", "audio", "video", "youtube", "ipynb",
]

# 8 MCP tools (this one included)
_TOOLS = [
    "extract_document", "batch_extract", "detect_format_tool",
    "generate_markdown", "generate_xliff", "save_skeleton",
    "ping", "validate_xliff", "get_capabilities",
]

# Note: validate_xliff was added in the prior session (commit 7ff9f04)


@mcp_error_boundary
async def get_capabilities(
    auth_token: Optional[str] = None,
) -> dict:
    """Return OPP capabilities for MCP clients.

    Returns a dict with:
        success (bool): True
        content.module (str): "opp"
        content.version (str | None): OPP version (best-effort)
        content.input_formats (list[str]): 16 input file formats
        content.output_formats (list[str]): ["md", "xliff", "both"]
        content.tools (list[str]): 8+ available MCP tool names
    """
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(
            code="AUTH_FAILED",
            message="Authentication failed: auth_token is missing or incorrect.",
        )

    version: str | None = None
    try:
        from opp import __version__ as _v  # type: ignore
        version = _v
    except Exception:
        pass

    return {
        "success": True,
        "content": {
            "module": "opp",
            "version": version,
            "input_formats": _INPUT_FORMATS,
            "output_formats": ["md", "xliff"],
            "tools": _TOOLS,
        },
    }
