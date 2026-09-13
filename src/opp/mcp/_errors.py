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
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

# S-4: shared exception types and validation helpers → re-export
from opp.utils.mcp_errors import (  # noqa: F401  (re-exported)
    MCPError,
    MAX_BATCH_FILES,
    MAX_BATCH_TEXTS,
    MAX_IMAGE_BYTES,
    ResourceExhausted,
    validate_batch_input,
    validate_file_paths,
    log_mcp_audit,
)
from opp.utils.security import PathValidationError  # noqa: F401 (re-exported)

_logger = logging.getLogger("opp_mcp.errors")


class McpError(Exception):
    """Raise to produce a standardized {success: false, error: {code, message}} response.

    Tool functions raise this instead of returning inline error dicts.
    The ``@mcp_error_boundary`` decorator catches it and formats the
    response with both the new nested ``error: {code, message}`` and
    the backward-compat flat ``error_code`` field.
    """

    def __init__(self, code: str, message: str, **extra: Any):
        self.code = code
        self.message = message
        self.extra = extra
        super().__init__(message)


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


# ── R-09: recovery hints ─────────────────────────────────────────────
# Hints are static constants: never interpolate the exception message or
# caller-controlled data (prompt-injection safety). Contract-tested by
# tests/contract/test_recovery_hints_contract.py.


@dataclass(frozen=True, slots=True)
class RecoveryHint:
    """A recoverability hint attached to a stable error code."""

    strategy: str
    hint: str


RECOVERY_HINTS: dict[str, RecoveryHint] = {
    "OPP_FILE_NOT_FOUND": RecoveryHint(
        "fix_input",
        "Verify the input path exists and is readable, then re-issue the call.",
    ),
    "OPP_PERMISSION_DENIED": RecoveryHint(
        "fix_input",
        "Check file and directory permissions for the server process, then re-issue.",
    ),
    "OPP_INVALID_INPUT": RecoveryHint(
        "fix_input",
        "Validate the request against the tool's input schema (format, required "
        "fields), then re-issue.",
    ),
    "OPP_MISSING_KEY": RecoveryHint(
        "fix_input",
        "Add the missing required field from the tool's input schema, then re-issue.",
    ),
    "OPP_TIMEOUT": RecoveryHint(
        "retry",
        "Retry with a smaller input, or raise OPP_MCP_TIMEOUT for large documents.",
    ),
    "OPP_NOT_IMPLEMENTED": RecoveryHint(
        "abort",
        "Do not retry; this code path is not implemented. File a feature request.",
    ),
    "OPP_PATH_DENIED": RecoveryHint(
        "use_allowed_path",
        "Use a path inside OPP_MCP_ALLOWED_DIRS (no '..', no escaping symlinks), "
        "then re-issue.",
    ),
    "OPP_RESOURCE_EXHAUSTED": RecoveryHint(
        "reduce_input",
        "Split the batch into smaller chunks or compress images, then re-issue.",
    ),
    "OPP_INTERNAL_ERROR": RecoveryHint(
        "report_bug",
        "Do not retry blindly; check server logs for the traceback and file a bug report.",
    ),
    "OPP_UNKNOWN_TOOL": RecoveryHint(
        "fix_input",
        "Call one of the advertised OPP tools; check the tool name spelling.",
    ),
    "AUTH_FAILED": RecoveryHint(
        "reissue_with_auth",
        "Re-issue the call with the correct auth_token matching MCP_SHARED_SECRET.",
    ),
    "RATE_LIMITED": RecoveryHint(
        "retry",
        "Wait for the rate-limit window to reset, then retry with lower concurrency.",
    ),
}

#: Every error code this module can emit — including AUTH_FAILED /
#: RATE_LIMITED / OPP_UNKNOWN_TOOL, which are raised by the server's
#: auth, rate-limit, and dispatch paths rather than by ``_ERROR_CODE_MAP``.
DECLARED_ERROR_CODES: frozenset[str] = (
    frozenset(_ERROR_CODE_MAP.values())
    | {"OPP_INTERNAL_ERROR", "OPP_UNKNOWN_TOOL", "AUTH_FAILED", "RATE_LIMITED"}
)

_FALLBACK_RECOVERY = RecoveryHint(
    "report_bug",
    "Unknown error code; inspect server logs for the traceback and file a bug report.",
)


def recovery_for(code: str) -> dict[str, str]:
    """Return the ``{strategy, hint}`` recovery envelope for *code*.

    Unknown codes receive a safe ``report_bug`` fallback, so every error
    envelope always carries a recovery object.
    """
    rec = RECOVERY_HINTS.get(code, _FALLBACK_RECOVERY)
    return {"strategy": rec.strategy, "hint": rec.hint}


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


def _format_error_response(exc: Exception) -> dict:
    """Build the standardized error response dict from an exception.

    If *exc* is a ``McpError``, use its explicit ``code`` and ``message``.
    Otherwise, classify via ``_ERROR_CODE_MAP`` and use a safe user message.
    Always includes the new nested ``error: {code, message}`` AND the
    backward-compat flat ``error_code`` field for one release cycle.
    """
    if isinstance(exc, McpError):
        code = exc.code
        msg = exc.message
        resp: dict[str, Any] = {
            "success": False,
            "error": {"code": code, "message": msg},
            "error_code": code,
            "message": msg,
            "recovery": recovery_for(code),
        }
        resp.update(exc.extra)
        return resp
    else:
        code = _classify(exc)
        msg = _safe_user_message(exc)
    return {
        "success": False,
        "error": {"code": code, "message": msg},
        # Backward-compat flat fields (kept for 1 release)
        "error_code": code,
        "message": msg,
        "recovery": recovery_for(code),
    }


def mcp_error_boundary(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: log full traceback server-side; return opaque error dict.

    OPP tools return dicts (not JSON strings). The wrapper preserves that
    shape and adds a stable ``error_code`` + safe ``message``. The ``error``
    field is now a dict ``{code, message}`` per the MCP I/O contract; the
    flat ``error_code`` and ``message`` are kept as backward-compat aliases.
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
            return _format_error_response(exc)

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
            return _format_error_response(exc)

    if inspect.iscoroutinefunction(fn):
        return async_wrapper
    return sync_wrapper
