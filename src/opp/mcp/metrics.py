"""Per-module Prometheus metrics for the OPP MCP server.

Phase 4.5: module-prefixed metrics (opp_*) emitted to a local
Prometheus text file under ``OMNI_METRICS_DIR`` (default
``/tmp/omni-metrics/opp.prom``). The shared ``omni_metrics`` package
(``omni_mcp_tool_calls_total`` etc.) is used for the suite-wide
aggregator; this module adds the OPP-specific counters and
histograms that the production-readiness plan requires.

Wired from ``server._handle_call_tool``. All write paths are
best-effort — metrics emission must NEVER raise into the request
path (would break the JSON-RPC stream).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    write_to_textfile,
)

_logger = logging.getLogger(__name__)

# Per-module registry — kept isolated from the global ``REGISTRY`` that
# ``omni_metrics`` uses, so the two metric families don't collide when
# both run in the same process (tests, docs/examples).
REGISTRY = CollectorRegistry()

# Histogram buckets required by the production-readiness plan.
_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

OPP_REQUESTS_TOTAL = Counter(
    "opp_requests_total",
    "Total OPP MCP requests, by tool_name and status.",
    ["tool_name", "status"],
    registry=REGISTRY,
)

OPP_REQUEST_DURATION_SECONDS = Histogram(
    "opp_request_duration_seconds",
    "OPP MCP request duration in seconds, by tool_name.",
    ["tool_name"],
    buckets=_DURATION_BUCKETS,
    registry=REGISTRY,
)

OPP_EXTRACTIONS_TOTAL = Counter(
    "opp_extractions_total",
    "Total OPP document extractions, by source format and status.",
    ["format", "status"],
    registry=REGISTRY,
)

# Status label values — stable strings; do not rename (clients may
# filter on them). The shared error boundary (``_errors.py``) returns
# its own ``error_code`` strings; we only need coarse-grained
# success/failure/rate_limited/auth_failed here.
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_AUTH_FAILED = "auth_failed"

# Cheap extension → format map for the call_tool dispatcher (the
# pipeline's magic-bytes detector is too expensive to call per
# request). Maps OPP's supported input formats to short labels.
_EXT_FORMAT_MAP = {
    ".docx": "docx",
    ".pptx": "pptx",
    ".pdf": "pdf",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".epub": "epub",
    ".eml": "eml",
    ".msg": "msg",
    ".md": "md",
    ".markdown": "md",
    ".ipynb": "ipynb",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".gif": "gif",
    ".bmp": "bmp",
    ".tiff": "tiff",
    ".tif": "tiff",
    ".webp": "webp",
    ".txt": "txt",
}


def classify_format_from_path(file_path: str | None) -> str:
    """Best-effort source format from a file path (extension)."""
    if not file_path:
        return "unknown"
    ext = os.path.splitext(str(file_path))[1].lower()
    return _EXT_FORMAT_MAP.get(ext, "unknown")


def _metrics_dir() -> Path:
    """Resolve metrics output directory; default ``/tmp/omni-metrics``."""
    return Path(os.environ.get("OMNI_METRICS_DIR", "/tmp/omni-metrics"))


_write_lock = threading.Lock()


def _emit() -> None:
    """Write the current registry to ``<OMNI_METRICS_DIR>/opp.prom``.

    Best-effort: never raises. ``write_to_textfile`` already
    renames atomically (.tmp → final) so concurrent scrapes see
    a complete file.
    """
    try:
        outdir = _metrics_dir()
        outdir.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            write_to_textfile(str(outdir / "opp.prom"), REGISTRY)
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_request(
    tool_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record a single OPP MCP request. Emits to file (best-effort)."""
    try:
        OPP_REQUESTS_TOTAL.labels(tool_name=tool_name, status=status).inc()
        OPP_REQUEST_DURATION_SECONDS.labels(tool_name=tool_name).observe(
            max(0.0, float(duration_seconds))
        )
        _emit()
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_extraction(format: str, status: str) -> None:
    """Record a single OPP extraction. ``format`` is the source file
    format (e.g. ``docx``, ``pdf``, ``json``); ``status`` is one of
    the ``STATUS_*`` constants.
    """
    try:
        OPP_EXTRACTIONS_TOTAL.labels(format=format or "unknown", status=status).inc()
        _emit()
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_request_from_arguments(
    tool_name: str,
    arguments: dict[str, Any] | None,
    status: str,
    duration_seconds: float,
) -> None:
    """Convenience: record a request and, for tools that operate on a
    file, also bump ``OPP_EXTRACTIONS_TOTAL`` by source format.
    """
    record_request(tool_name, status, duration_seconds)
    args = arguments or {}
    if tool_name in ("extract_document", "generate_xliff", "generate_markdown", "save_skeleton"):
        record_extraction(classify_format_from_path(args.get("file_path")), status)
    elif tool_name == "batch_extract":
        # Use the first file's format as a coarse label.
        paths = args.get("file_paths") or []
        if paths:
            record_extraction(classify_format_from_path(paths[0]), status)
    elif tool_name == "detect_format_tool":
        # detect_format_tool is not an extraction; skip the extraction counter.
        pass


def time_block() -> "_OPPBlockTimer":
    """Return a context-manager-style timer for use in the dispatcher."""
    return _OPPBlockTimer()


class _OPPBlockTimer:
    """Lightweight wall-clock timer for the ``call_tool`` dispatcher."""

    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0 = time.monotonic()

    def seconds(self) -> float:
        return max(0.0, time.monotonic() - self._t0)


__all__ = [
    "REGISTRY",
    "OPP_REQUESTS_TOTAL",
    "OPP_REQUEST_DURATION_SECONDS",
    "OPP_EXTRACTIONS_TOTAL",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_RATE_LIMITED",
    "STATUS_AUTH_FAILED",
    "classify_format_from_path",
    "record_request",
    "record_extraction",
    "record_request_from_arguments",
    "time_block",
]
