"""C12: shared error boundary for OPP MCP tools.

This module provides a single ``@mcp_error_boundary`` decorator that replaces
the multiple ``try/except Exception as e: return ...str(e)...`` copies in
``opp/mcp/server.py``.

S-4 consolidation — shared exception types and validation helpers are
imported from ``opp.utils.mcp_errors`` and re-exported here so existing
importers are unaffected.

Behavior:
- Log the full traceback at ERROR level server-side.
- Return a dict with ``success=False``, an opaque ``error_code`` (mapped
  from exception class), and a user-friendly ``message`` (no internals).
- For exceptions, also append a stable "error" string for clients that
  key off that field (preserving backward compat with test assertions
  that check ``result["error"]`` is truthy).
- M-2: emit structured audit log entry for every tool call (timing +
  success/failure).
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any
from collections.abc import Callable

# S-4: shared exception types and validation helpers → re-export
from opp.utils.mcp_errors import (  # noqa: F401  (re-exported)
    MCPError,
    MAX_BATCH_FILES,
    MAX_BATCH_TEXTS,
    MAX_IMAGE_BYTES,
    PathValidationError,
    ResourceExhausted,
    validate_batch_input,
    validate_file_paths,
    log_mcp_audit,
)

_logger = logging.getLogger("opp_mcp.errors")

_ERROR_CODE_MAP: dict[type, str] = {
    FileNotFoundError: "OPP_FILE_NOT_FOUND",
    PermissionError: "OPP_PERMISSION_DENIED",
    ValueError: "OPP_INVALID_INPUT",
    KeyError: "OPP_MISSING_KEY",
    TimeoutError: "OPP_TIMEOUT",
    NotImplementedError: "OPP_NOT_IMPLEMENTED",
    PathValidationError: "OPP_PATH_DENIED",
    ResourceExhausted: "OPP_RESOURCE_EXHAUSTED",
}


def _classify(exc: BaseException) -> str:
    for klass, code in _ERROR_CODE_MAP.items():
        if isinstance(exc, klass):
            return code
    return "OPP_INTERNAL_ERROR"


def _safe_user_message(exc: BaseException) -> str:
    code = _classify(exc)
    return {
        "OPP_FILE_NOT_FOUND": "A required file was not found.",
        "OPP_PERMISSION_DENIED": "Permission denied for the requested operation.",
        "OPP_INVALID_INPUT": "The request input was invalid.",
        "OPP_MISSING_KEY": "A required key was missing from the input.",
        "OPP_TIMEOUT": "The operation timed out.",
        "OPP_NOT_IMPLEMENTED": "The requested feature is not yet implemented.",
        "OPP_PATH_DENIED": "Access to the requested path was denied.",
        "OPP_RESOURCE_EXHAUSTED": "The operation exceeded resource limits.",
        "OPP_INTERNAL_ERROR": "An internal error occurred. Check server logs.",
    }.get(code, "An internal error occurred. Check server logs.")


def mcp_error_boundary(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: log full traceback server-side; return opaque error dict.

    OPP tools return dicts (not JSON strings). The wrapper preserves that
    shape and adds a stable ``error_code`` + safe ``message``. The ``error``
    field is kept (with the safe message) for backward compat with
    existing test assertions.
    """

    tool_name = getattr(fn, "__name__", "<unknown>")

    @functools.wraps(fn)
    async def async_wrapper(*args: Any, **kwargs: Any):
        t0 = time.time()
        try:
            result = await fn(*args, **kwargs)
            log_mcp_audit(tool_name, (time.time() - t0) * 1000, True)
            return result
        except Exception as exc:
            log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
            _logger.exception(
                "MCP tool %s raised: %s",
                tool_name,
                exc,
            )
            code = _classify(exc)
            return {
                "success": False,
                "error_code": code,
                "message": _safe_user_message(exc),
                "error": _safe_user_message(exc),
            }

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any):
        t0 = time.time()
        try:
            result = fn(*args, **kwargs)
            log_mcp_audit(tool_name, (time.time() - t0) * 1000, True)
            return result
        except Exception as exc:
            log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
            _logger.exception(
                "MCP tool %s raised: %s",
                tool_name,
                exc,
            )
            code = _classify(exc)
            return {
                "success": False,
                "error_code": code,
                "message": _safe_user_message(exc),
                "error": _safe_user_message(exc),
            }

    if inspect.iscoroutinefunction(fn):
        return async_wrapper
    return sync_wrapper
