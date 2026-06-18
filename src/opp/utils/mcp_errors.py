"""S-4 / S-5: shared MCP error boundary decorator and resource validation.

Consolidates error handling across OPP, OL, and ORF MCP servers.

Provides:
  - Custom exception classes for MCP-specific error conditions.
  - ``mcp_error_boundary(tool_name)`` parameterised decorator — catches
    known errors, returns opaque dict responses, and logs audit entries
    with timing (M-2 audit logging).
  - Validation helpers to enforce batch and file-size limits.
  - ``get_audit_logger()`` and ``log_mcp_audit()`` for M-2 audit logging
    across all three MCP servers.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar

_logger = logging.getLogger("opp.mcp_errors")

# ---------------------------------------------------------------------------
# M-2: Audit logging (shared across OPP / OL / ORF MCP servers)
# ---------------------------------------------------------------------------

_AUDIT_LOG_DIR = Path("logs")
_AUDIT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_AUDIT_BACKUP_COUNT = 5
_audit_logger: logging.Logger | None = None


def get_audit_logger() -> logging.Logger:
    """Return the shared M-2 audit logger (one-per-process).

    Writes structured JSON entries to ``logs/audit_{date}.log`` with
    rotation at 10 MB (5 backups).  Pattern follows ORF's audit logger
    (``orf/logging/__init__.py``) but uses JSON-formatted messages to
    match the M-2 requirement:

        {"event": "mcp_call", "tool": "...", "duration_ms": 1234, "success": true}
    """
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    _AUDIT_LOG_DIR.mkdir(exist_ok=True, parents=True)
    audit_file = _AUDIT_LOG_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("opp.mcp_audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # keep audit entries out of root logger

    if not logger.handlers:
        handler = RotatingFileHandler(
            audit_file,
            maxBytes=_AUDIT_MAX_BYTES,
            backupCount=_AUDIT_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setLevel(logging.INFO)
        # JSON lines — no decorator prefix, just the raw JSON object per line
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _audit_logger = logger
    return _audit_logger


def log_mcp_audit(tool_name: str, duration_ms: float, success: bool) -> None:
    """Emit a single structured audit line for an MCP tool call.

    Must NOT include secrets, API keys, or any sensitive data.  Only the
    three fields defined by M-2 are logged.
    """
    try:
        entry = {
            "event": "mcp_call",
            "tool": tool_name,
            "duration_ms": round(duration_ms, 3),
            "success": success,
        }
        get_audit_logger().info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        # Audit logging must never break the tool call.
        pass
    # 2026-06-18 round 16 Phase B5: Prometheus metrics.
    # Import lazily — omni_metrics is in the main repo, not a submodule dep.
    try:
        import os as _os
        _suite_root = _os.path.dirname(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        )
        if _suite_root not in _os.sys.path:
            _os.sys.path.insert(0, _suite_root)
        from omni_metrics import record_tool_call
        record_tool_call("opp", tool_name, duration_ms, success)
    except Exception:
        pass

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# S-5: Resource limits
# ---------------------------------------------------------------------------

MAX_BATCH_TEXTS: int = 100
MAX_BATCH_FILES: int = 50
MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10 MiB


# ---------------------------------------------------------------------------
# S-4: Exception hierarchy
# ---------------------------------------------------------------------------

class MCPError(Exception):
    """Base for MCP-specific errors."""


class PathValidationError(MCPError):
    """Path outside allowed directories."""


class ResourceExhausted(MCPError):
    """Batch / file-size limit exceeded."""


# ---------------------------------------------------------------------------
# S-5: Validation helpers
# ---------------------------------------------------------------------------

def validate_batch_input(texts: list[str]) -> list[str]:
    """Raise ResourceExhausted if *texts* exceeds MAX_BATCH_TEXTS."""
    if len(texts) > MAX_BATCH_TEXTS:
        raise ResourceExhausted(
            f"Batch size {len(texts)} exceeds limit {MAX_BATCH_TEXTS}"
        )
    return texts


def validate_file_paths(paths: list[str]) -> list[str]:
    """Raise ResourceExhausted if *paths* exceeds MAX_BATCH_FILES."""
    if len(paths) > MAX_BATCH_FILES:
        raise ResourceExhausted(
            f"File count {len(paths)} exceeds limit {MAX_BATCH_FILES}"
        )
    return paths


# ---------------------------------------------------------------------------
# S-4: parameterised error boundary decorator
# ---------------------------------------------------------------------------

def mcp_error_boundary(tool_name: str) -> Callable[[F], F]:
    """Decorator factory: wrap an MCP tool so uncaught exceptions produce
    opaque, structured error dicts.

    Usage::

        @mcp_error_boundary("extract_document")
        async def extract_document(file_path: str, ...) -> dict:
            ...

    On success the wrapped function's return value is passed through
    unmodified (backward-compatible with existing OPP/OL/ORF tool
    response shapes).

    On failure it returns a dict with::

        {"success": False, "error": "<code>", "code": <http_status>}

    where *code* is one of ``ACCESS_DENIED``, ``RATE_LIMITED``, or
    ``INTERNAL_ERROR``.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.time()
            try:
                result = await func(*args, **kwargs)
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, True)
                return result
            except PathValidationError:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.warning("MCP %s: path denied", tool_name)
                return {
                    "success": False,
                    "error": "ACCESS_DENIED",
                    "code": 403,
                }
            except ResourceExhausted:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.warning("MCP %s: resource exhausted", tool_name)
                return {
                    "success": False,
                    "error": "RATE_LIMITED",
                    "code": 429,
                }
            except Exception:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.exception("MCP %s failed", tool_name)
                return {
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "code": 500,
                }

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.time()
            try:
                result = func(*args, **kwargs)
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, True)
                return result
            except PathValidationError:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.warning("MCP %s: path denied", tool_name)
                return {
                    "success": False,
                    "error": "ACCESS_DENIED",
                    "code": 403,
                }
            except ResourceExhausted:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.warning("MCP %s: resource exhausted", tool_name)
                return {
                    "success": False,
                    "error": "RATE_LIMITED",
                    "code": 429,
                }
            except Exception:
                log_mcp_audit(tool_name, (time.time() - t0) * 1000, False)
                _logger.exception("MCP %s failed", tool_name)
                return {
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "code": 500,
                }

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
