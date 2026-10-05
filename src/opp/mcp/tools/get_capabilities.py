"""get_capabilities tool for OPP.

Returns module-level static information about what the OPP MCP server
can do. This is the "self-description" feature requested by agents.
"""
from __future__ import annotations

from opp.extractors.html.markdown_converter import MARKDOWNIFY_AVAILABLE
from opp.mcp._errors import McpError, mcp_error_boundary
from opp.mcp.auth import check_auth
from opp.mcp.rate_limiter import check_rate_limit

# 16 input formats (must match opp/extractors/__init__.py)
_INPUT_FORMATS = [
    "docx", "pptx", "pdf", "xlsx", "csv", "json", "xml", "html",
    "epub", "eml", "msg", "image", "audio", "video", "youtube", "ipynb",
]

# 9 MCP tools (this one included)
_TOOLS = [
    "extract_document", "batch_extract", "detect_format_tool",
    "generate_markdown", "generate_xliff", "save_skeleton",
    "ping", "validate_xliff", "get_capabilities",
]

# Note: validate_xliff was added in the prior session (commit 7ff9f04)


@mcp_error_boundary
async def get_capabilities(
    auth_token: str | None = None,
) -> dict:
    """Return OPP capabilities for MCP clients.

    Returns a dict with:
        success (bool): True
        content.module (str): "opp"
        content.version (str | None): OPP version (best-effort)
        content.input_formats (list[str]): 16 input file formats
        content.output_formats (list[str]): ["md", "xliff"]
        content.tools (list[str]): 9 available MCP tool names
        content.degradations (list[str]): optional-dependency degradations
            currently active; empty when the install is complete
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
    except Exception:  # expected: version fetch is best-effort
        pass

    # Surface optional-dependency degradation up front. An agent that reads
    # "html: supported" and calls extract_document has no other way to learn
    # that HTML extraction is running in a reduced mode until it inspects the
    # per-call warnings. Same string style as ExtractionResult.warnings so the
    # two are recognisably the same channel.
    degradations: list[str] = []
    if not MARKDOWNIFY_AVAILABLE:
        degradations.append(
            "markdownify不可用：HTML→Markdown降级为原文透传，"
            "段落边界与骨架可能丢失（pip install 'omni-pre-processor[web]' 可修复）"
        )

    return {
        "success": True,
        "content": {
            "module": "opp",
            "version": version,
            "input_formats": _INPUT_FORMATS,
            "output_formats": ["md", "xliff"],
            "tools": _TOOLS,
            "degradations": degradations,
        },
    }
