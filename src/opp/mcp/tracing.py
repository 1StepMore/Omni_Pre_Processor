"""OTel tracing for the OPP MCP server.

Phase 4.5: distributed tracing (not metrics) for the OPP MCP
dispatcher.  Spans are emitted when ``OMNI_TRACING_ENABLED=1``;
otherwise the tracer is a no-op (the default) so tests and
production runs without observability configured see zero
overhead.

The exporter is a tiny custom JSONL file exporter
(``_JsonlFileSpanExporter``) that writes one line per span to
``OMNI_TRACES_DIR/opp.jsonl`` (default ``/tmp/omni-traces/``).
We avoid the OTLP/gRPC exporter because (a) it requires network
setup and (b) the production-readiness plan forbids adding new
dependencies — only ``opentelemetry-api`` + ``opentelemetry-sdk``
are guaranteed to be installed.

The exporter is **never** the OTel ConsoleSpanExporter (which
prints to stdout and would corrupt the MCP JSON-RPC stream) and
is **never** wired up unless ``OMNI_TRACING_ENABLED=1`` is set.

Wired from ``server._handle_call_tool`` via
``start_call_tool_span`` + ``record_call_tool_result``.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_logger = logging.getLogger(__name__)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from opentelemetry.context import Context

MODULE_NAME = "opp"
SPAN_NAME_CALL_TOOL = "opp.call_tool"
_TRACER_NAME = "opp"

# Stable attribute keys — clients may filter on them.
ATTR_TOOL_NAME = "tool.name"
ATTR_TOOL_STATUS = "tool.status"
ATTR_TOOL_DURATION_MS = "tool.duration_ms"
ATTR_TOOL_ERROR_CODE = "tool.error_code"
ATTR_MODULE = "module"
ATTR_MODULE_VERSION = "module.version"


def is_enabled() -> bool:
    """Return True if tracing is enabled via env var.

    Default: disabled (matches the metrics convention
    ``OMNI_METRICS_DIR`` is read always but writes are
    best-effort; tracing requires explicit opt-in because spans
    have per-request overhead).
    """
    val = os.environ.get("OMNI_TRACING_ENABLED", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def _traces_dir() -> Path:
    return Path(os.environ.get("OMNI_TRACES_DIR", "/tmp/omni-traces"))


class _JsonlFileSpanExporter(SpanExporter):
    """SpanExporter that writes one JSON line per span to a file.

    Thread-safe (writes are serialized via a lock).  Never raises
    into the request path (export failures are swallowed; the
    ``SimpleSpanProcessor`` already records them in the
    provider-level error counter).
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:  # type: ignore[override]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with self._path.open("a", encoding="utf-8") as fh:
                    for span in spans:
                        try:
                            ctx = span.get_span_context()
                            parent_id = (
                                format(span.parent.span_id, "016x")
                                if span.parent is not None
                                else None
                            )
                            payload = {
                                "name": span.name,
                                "trace_id": format(ctx.trace_id, "032x"),
                                "span_id": format(ctx.span_id, "016x"),
                                "parent_span_id": parent_id,
                                "start_time_ns": span.start_time,
                                "end_time_ns": span.end_time,
                                "duration_ms": max(
                                    0.0,
                                    (span.end_time - span.start_time) / 1_000_000.0,
                                ),
                                "status": {
                                    "status_code": span.status.status_code.name
                                    if span.status is not None
                                    else "UNSET",
                                    "description": span.status.description
                                    if span.status is not None
                                    else "",
                                },
                                "attributes": dict(span.attributes or {}),
                                "resource": {
                                    k: v for k, v in (span.resource.attributes.items()
                                                      if span.resource is not None
                                                      else [])
                                },
                            }
                            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
                        except Exception:
                            _logger.debug("Skipping span serialization due to error")  # expected — single-span failure must not break export
                            continue
        except Exception:
            _logger.debug("Span export failed")  # expected — export failure returns FAILURE per OTel contract
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


_setup_lock = threading.Lock()
_setup_done = False


def setup_tracing() -> bool:
    """Initialize the global TracerProvider with a JSONL file
    exporter.  Returns True if tracing is now active.

    Idempotent — safe to call multiple times.  Does nothing if
    tracing is disabled.
    """
    global _setup_done
    if not is_enabled():
        return False
    with _setup_lock:
        if _setup_done:
            return True
        provider = TracerProvider()
        out = _traces_dir() / f"{MODULE_NAME}.jsonl"
        provider.add_span_processor(SimpleSpanProcessor(_JsonlFileSpanExporter(out)))
        trace.set_tracer_provider(provider)
        _setup_done = True
        return True


def get_tracer() -> Tracer:
    """Return the OPP tracer.  Triggers setup on first call."""
    setup_tracing()
    return trace.get_tracer(_TRACER_NAME)


def _version() -> str:
    try:
        from opp import __version__
        return str(__version__)
    except Exception:  # expected — package metadata unavailable
        return "unknown"


def _extract_traceparent_context(traceparent: str) -> Context | None:
    """Parse a W3C ``traceparent`` string and return an OTel Context.

    Returns None if the traceparent is invalid or cannot be parsed.
    The returned Context is suitable for passing as ``context=`` to
    ``tracer.start_as_current_span(...)`` so the new span becomes a
    child of the upstream span identified by the traceparent.
    """
    if not traceparent:
        return None
    try:
        return TraceContextTextMapPropagator().extract({"traceparent": traceparent})
    except Exception:  # expected — invalid traceparent is benign
        return None


def inject_traceparent(span: Span | None) -> str | None:
    """Build a W3C ``traceparent`` string from the given span's context.

    Format: ``00-{32-hex-trace-id}-{16-hex-span-id}-{2-hex-flags}``

    Returns None if the span is None or has an invalid context.
    The flags are ``01`` (sampled) or ``00`` (not sampled).
    """
    if span is None:
        return None
    try:
        ctx = span.get_span_context()
    except Exception:  # expected — invalid span context is benign
        return None
    if ctx is None or not ctx.is_valid:
        return None
    flags = "01" if ctx.trace_flags.sampled else "00"
    return f"00-{format(ctx.trace_id, '032x')}-{format(ctx.span_id, '016x')}-{flags}"


@contextmanager
def start_call_tool_span(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    traceparent: str | None = None,
) -> Iterator[Span | None]:
    """Context manager: start an ``opp.call_tool`` span (or yield
    ``None`` if tracing is disabled).  Yields a ``Span`` that the
    caller can attach status/error info to.

    On exit, the span is automatically ended by OTel.  The caller
    is responsible for setting status via ``set_span_status`` and
    emitting the result.

    If ``traceparent`` is provided (W3C Trace Context format), the
    new span becomes a child of the span identified by the
    traceparent.  This is the cross-module propagation hook used
    by OPP/OL/ORF to thread a single trace across the pipeline.

    Example::

        with start_call_tool_span("extract_document", args) as span:
            try:
                result = await fn(**(args or {}))
                set_span_status(span, "success")
            except Exception as e:
                set_span_status(span, "error", error_code=type(e).__name__)
                raise
    """
    if not is_enabled():
        yield None
        return
    tracer = get_tracer()
    parent_ctx = _extract_traceparent_context(traceparent) if traceparent else None
    with tracer.start_as_current_span(SPAN_NAME_CALL_TOOL, context=parent_ctx) as span:
        try:
            span.set_attribute(ATTR_MODULE, MODULE_NAME)
            span.set_attribute(ATTR_MODULE_VERSION, _version())
            span.set_attribute(ATTR_TOOL_NAME, tool_name)
            yield span
        except Exception:
            raise


def set_span_status(
    span: Span | None,
    status: str,
    error_code: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Attach a status attribute to the span and mark the OTel
    span status accordingly.  No-op if span is None (tracing
    disabled) or if the span is not recording.
    """
    if span is None:
        return
    if not span.is_recording():
        return
    span.set_attribute(ATTR_TOOL_STATUS, status)
    if error_code is not None:
        span.set_attribute(ATTR_TOOL_ERROR_CODE, error_code)
    if duration_ms is not None:
        span.set_attribute(ATTR_TOOL_DURATION_MS, float(duration_ms))
    if status == "success":
        span.set_status(Status(StatusCode.OK))
    elif status in ("error", "rate_limited", "auth_failed"):
        span.set_status(
            Status(StatusCode.ERROR, description=error_code or status)
        )


def _tracing_file_path() -> Path:
    return _traces_dir() / f"{MODULE_NAME}.jsonl"


__all__ = [
    "MODULE_NAME",
    "SPAN_NAME_CALL_TOOL",
    "ATTR_TOOL_NAME",
    "ATTR_TOOL_STATUS",
    "ATTR_TOOL_DURATION_MS",
    "ATTR_TOOL_ERROR_CODE",
    "is_enabled",
    "setup_tracing",
    "get_tracer",
    "start_call_tool_span",
    "set_span_status",
    "inject_traceparent",
    "_extract_traceparent_context",
    "_tracing_file_path",
]
