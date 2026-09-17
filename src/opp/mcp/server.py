"""OPP MCP Server using the standard mcp library.

Replaces the previous fastmcp-based implementation. Uses
``mcp.server.Server`` + ``mcp.server.stdio.stdio_server`` for the
transport layer.

Tool functions have been split into the ``opp.mcp.tools`` package for
maintainability. This module re-exports them (so existing direct-call
tests such as ``opp.mcp.server.extract_document(...)`` keep working)
and provides the MCP transport layer (Server, stdio, tool registration,
dispatch).

Security layers preserved on all seven tool functions:
- ``@mcp_error_boundary`` decorator
- ``check_rate_limit()`` (token bucket)
- ``check_auth(auth_token)`` (shared-secret)
- ``PathValidator`` (allowlist, size, traversal, symlinks)
- ``_safe_unlink()``, ``_safe_temp_output()`` (C3 fix)

Re-exports (backward compat for ``from opp.mcp.server import ...``):
  ping, detect_format_tool, save_skeleton, generate_markdown,
  generate_xliff, extract_document, batch_extract, _init_server
"""

from __future__ import annotations

import json
import os
import signal as _signal
from typing import Any

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from opp.mcp import common as _common
from opp.mcp.common import (_init_server, _signal_handler, logger)
from opp.mcp.config import load_config
from opp.mcp.health import start_health_server as _health_start
from opp.mcp.metrics import (
    STATUS_AUTH_FAILED as _STATUS_AUTH_FAILED,
    STATUS_ERROR as _STATUS_ERROR,
    STATUS_RATE_LIMITED as _STATUS_RATE_LIMITED,
    STATUS_SUCCESS as _STATUS_SUCCESS,
    record_request_from_arguments,
    time_block as _metrics_timer,
)
from opp.mcp.tracing import (
    set_span_status as _tracing_set_status,
    start_call_tool_span as _tracing_start_span,
    inject_traceparent as _tracing_inject_traceparent,
)

# Import all tool functions (re-exported at this module for backward compat)
from opp.mcp.tools import (
    batch_extract,
    detect_format_tool,
    extract_document,
    generate_markdown,
    generate_xliff,
    ping,
    save_skeleton,
    validate_xliff,
    get_capabilities,
)

__all__ = [
    "batch_extract",
    "detect_format_tool",
    "extract_document",
    "generate_markdown",
    "generate_xliff",
    "ping",
    "save_skeleton",
    "validate_xliff",
    "get_capabilities",
    "_init_server",
]


def __getattr__(name: str) -> Any:
    """Delegate attribute access to ``common`` module for mutable state.

    PEP 562 module-level ``__getattr__``. This ensures that ``server._validator``,
    ``server._config``, etc. always reflect the current state set by
    ``_init_server()``, even though those names live in ``opp.mcp.common``.
    """
    if name in ("_config", "_validator", "_pipeline", "_serializer", "_tempfiles"):
        return getattr(_common, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


# ─────────────────────────────────────────────────────────────────────
# Tool schemas exposed to MCP clients (used by @server.list_tools())
# ─────────────────────────────────────────────────────────────────────

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "extract_document",
        "description": (
            "Extract content from a single document file. Supports DOCX, PPTX, "
            "PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and images. "
            "Returns markdown and/or XLIFF depending on output_formats."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the source document."},
                "output_formats": {
                    "oneOf": [
                        {"type": "string", "enum": ["md", "xlf", "both"]},
                        {
                            "type": "array",
                            "items": {"type": "string", "enum": ["md", "xlf", "both"]},
                        },
                    ],
                    "description": "Output formats; default is ['md'].",
                },
                "source_lang": {"type": "string", "default": "zh", "description": "Source language code."},
                "target_lang": {"type": "string", "default": "en", "description": "Target language code."},
                "resource_dir": {"type": "string", "description": "Directory to store extracted resources."},
                "verbose": {"type": "boolean", "default": False, "description": "Include extra metadata (detected_format, confidence, processing_steps) in the response."},
                "ocr_lang": {"type": "string", "description": "OCR language code (e.g. 'chi_sim', 'jpn', 'fra'). Sets OPP_OCR_LANG env var before extraction. Default: 'eng'."},
                "traceparent": {
                    "type": "string",
                    "description": "Optional W3C Trace Context traceparent header to make this span a child of an upstream trace.",
                },
                "auth_token": {"type": "string", "description": "Shared secret for MCP auth (when MCP_SHARED_SECRET is set)."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "batch_extract",
        "description": (
            "Process multiple files in one request. Returns per-file extraction "
            "results plus aggregate counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of absolute file paths to extract.",
                },
                "output_formats": {
                    "oneOf": [
                        {"type": "string", "enum": ["md", "xlf", "both"]},
                        {
                            "type": "array",
                            "items": {"type": "string", "enum": ["md", "xlf", "both"]},
                        },
                    ],
                    "description": "Output formats; default is ['md'].",
                },
                "source_lang": {"type": "string", "default": "zh"},
                "target_lang": {"type": "string", "default": "en"},
                "auth_token": {"type": "string"},
            },
            "required": ["file_paths"],
        },
    },
    {
        "name": "detect_format_tool",
        "description": (
            "Identify the file format using magic-bytes detection. Returns "
            "the format name and a confidence score in [0, 1]."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file to inspect."},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "generate_xliff",
        "description": (
            "Convert a document to XLIFF format for translation workflows. "
            "Requires source and target language codes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "source_lang": {"type": "string", "default": "zh"},
                "target_lang": {"type": "string", "default": "en"},
                "output_path": {"type": "string", "description": "Optional output XLIFF path."},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "generate_markdown",
        "description": "Convert a document to Markdown format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "output_path": {"type": "string"},
                "style_mapping": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                    "description": "Optional mapping from style name to heading level.",
                },
                "embed_images": {"type": "boolean", "default": True},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "save_skeleton",
        "description": (
            "Save skeleton ZIP from an extracted DOCX/PPTX. The skeleton is "
            "required by ORF's apply_xliff for XLIFF->DOCX/PPTX backfill."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "base_name": {"type": "string", "default": "document"},
                "output_dir": {"type": "string"},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "ping",
        "description": "Health check endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "auth_token": {"type": "string"},
            },
        },
    },
    {
        "name": "validate_xliff",
        "description": (
            "Validate an XLIFF 1.2 file against the OASIS XSD schema and the "
            "trans-unit content rules (non-empty source, unique IDs, valid lang codes). "
            "Pass either xliff_content (inline string) or file_path."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "xliff_content": {
                    "type": "string",
                    "description": "Inline XLIFF XML. Takes precedence over file_path if both provided.",
                },
                "file_path": {
                    "type": "string",
                     "description": "Path to .xlf/.xliff file. Used only if xliff_content is not provided.",
                 },
                 "auth_token": {"type": "string"},
             },
         },
     },
     {
         "name": "get_capabilities",
         "description": (
             "Return OPP module capabilities: supported input formats (16), "
             "output formats (md/xliff), and the list of available MCP tools. "
             "Use this to discover what the server can do at runtime."
         ),
         "inputSchema": {
             "type": "object",
             "properties": {
                 "auth_token": {"type": "string"},
             },
         },
     },
]


# ─────────────────────────────────────────────────────────────────────
# Dispatch table: tool name -> module-level async function
# ─────────────────────────────────────────────────────────────────────

_TOOL_DISPATCH: dict[str, Any] = {
    "extract_document": extract_document,
    "batch_extract": batch_extract,
    "detect_format_tool": detect_format_tool,
    "generate_xliff": generate_xliff,
    "generate_markdown": generate_markdown,
    "save_skeleton": save_skeleton,
    "ping": ping,
    "validate_xliff": validate_xliff,
    "get_capabilities": get_capabilities,
}


# Build the standard mcp Server instance.
server: Server = Server("opp-mcp")


@server.list_tools()
async def _handle_list_tools() -> list[types.Tool]:
    return [types.Tool(**schema) for schema in _TOOL_SCHEMAS]


@server.call_tool()
async def _handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Dispatch a tool call to the appropriate module-level function.

    The ``mcp_error_boundary`` decorator on the tool functions already
    converts uncaught exceptions into safe error dicts, but the standard
    mcp library doesn't handle exceptions raised by ``call_tool`` the
    same way FastMCP did. The wrapper below provides an additional
    safety net: any exception that escapes the decorator is logged with
    full traceback server-side (via ``logger.exception`` below) and
    returned to the client as an opaque error response (no internals
    leaked).
    """
    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        record_request_from_arguments(
            name, arguments, _STATUS_ERROR, 0.0,
        )
        with _tracing_start_span(name, arguments) as _span:
            _tracing_set_status(_span, "error", error_code="OPP_UNKNOWN_TOOL")
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "OPP_UNKNOWN_TOOL",
                            "message": f"Unknown tool: {name!r}",
                        },
                        "error_code": "OPP_UNKNOWN_TOOL",
                        "message": f"Unknown tool: {name!r}",
                    }
                ),
            )
        ]

    timer = _metrics_timer()
    _traceparent_arg = (arguments or {}).get("traceparent")
    with _tracing_start_span(name, arguments, traceparent=_traceparent_arg) as _span:
        try:
            result = await fn(**(arguments or {}))
        except Exception:
            duration = timer.seconds()
            logger.exception("Unhandled error in tool %s", name)
            record_request_from_arguments(
                name, arguments, _STATUS_ERROR, duration,
            )
            _tracing_set_status(
                _span, "error",
                error_code="OPP_INTERNAL_ERROR",
                duration_ms=duration * 1000.0,
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "OPP_INTERNAL_ERROR",
                                "message": "An internal error occurred. Check server logs.",
                            },
                            "error_code": "OPP_INTERNAL_ERROR",
                            "message": "An internal error occurred. Check server logs.",
                            "tool": name,
                        }
                    ),
                )
            ]

        if not isinstance(result, dict):
            result = {"success": True, "content": {"data": result}}

        if (
            name == "extract_document"
            and isinstance(result, dict)
            and isinstance(result.get("content"), dict)
        ):
            tp = _tracing_inject_traceparent(_span)
            if tp is not None:
                result["content"]["traceparent"] = tp

        status = _classify_status(result)
        record_request_from_arguments(
            name, arguments, status, timer.seconds(),
        )
        _tracing_set_status(
            _span, status,
            error_code=result.get("error_code") if isinstance(result, dict) else None,
            duration_ms=timer.seconds() * 1000.0,
        )

        return [
            types.TextContent(
                type="text", text=json.dumps(result, ensure_ascii=False)
            )
        ]


def _classify_status(result: dict[str, Any]) -> str:
    """Map a tool's result dict to a coarse status label for metrics."""
    if not isinstance(result, dict):
        return _STATUS_ERROR
    if result.get("success") is True:
        return _STATUS_SUCCESS
    code = result.get("error_code")
    if code == "RATE_LIMITED":
        return _STATUS_RATE_LIMITED
    if code == "AUTH_FAILED":
        return _STATUS_AUTH_FAILED
    return _STATUS_ERROR


# ─────────────────────────────────────────────────────────────────────
# Transport layer
# ─────────────────────────────────────────────────────────────────────

async def _run() -> None:
    """Async entry point: drive the stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
            raise_exceptions=False,
        )


def main() -> None:
    """Synchronous entry point invoked by ``python -m opp.mcp.server``."""
    config = load_config()
    _init_server(config)
    _health_start()
    if not os.environ.get("OPP_MCP_DISABLE_SIGNAL_HANDLERS"):
        try:
            _signal.signal(_signal.SIGTERM, _signal_handler)
            _signal.signal(_signal.SIGINT, _signal_handler)
            logger.debug("OPP#10: installed SIGTERM/SIGINT handlers")
        except (ValueError, OSError):
            pass
    anyio.run(_run)


if __name__ == "__main__":
    main()
