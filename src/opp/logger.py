"""Structured JSON logging for OPP via structlog.

Public API:
- ``logger`` — module-level stdlib logger (back-compat: ``.name`` + isinstance)
- ``setup_logger(verbose=False)`` — initialize file handler + configure structlog
- ``get_logger(name=None)`` — return the stdlib root or child logger
- ``bind_request_id(rid)`` / ``clear_request_id()`` — contextvar helpers
- ``_build_formatter(json_mode)`` — back-compat shim for legacy stdlib tests

JSON shape (when ``OMNI_LOG_FORMAT=json``):
    {"timestamp": "2026-06-22T...", "level": "INFO", "module": "opp.cli",
     "request_id": "abc-123", "event": "extraction_complete", **kwargs}

Text shape (default):
    [2026-06-22 06:00:00] [INFO] [opp.cli] extraction_complete file=/tmp/doc.md

New code should use ``structlog.get_logger("opp.<name>").info(event, k=v)``
to get kwargs-as-fields behavior. Both paths route through the same
stdlib logger and produce the same JSON shape.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

_LOG_DIR: Path = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_logger_configured = False


def _uppercase_level(_logger: Any, _method_name: str, event_dict: dict) -> dict:
    if "level" in event_dict:
        event_dict["level"] = event_dict["level"].upper()
    return event_dict


def _add_module_field(_logger: Any, _method_name: str, event_dict: dict) -> dict:
    name = event_dict.pop("logger", None)
    if name is not None and "module" not in event_dict:
        event_dict["module"] = name
    return event_dict


def _is_json_mode() -> bool:
    return os.environ.get("OMNI_LOG_FORMAT", "console").lower() == "json"


def _build_processors() -> list:
    """Pre-processors that run on the LogRecord via ProcessorFormatter.

    The final renderer is NOT included here — it is supplied separately
    to ``ProcessorFormatter.processor``. Keeping the chain renderer-less
    prevents structlog from double-rendering when both structlog and
    stdlib handler formatters are active.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.ExtraAdder(),
        structlog.stdlib.add_logger_name,
        _add_module_field,
        structlog.stdlib.add_log_level,
        _uppercase_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _build_final_renderer() -> Any:
    """Return the final renderer (JSON in json mode, ConsoleRenderer otherwise)."""
    if _is_json_mode():
        return structlog.processors.JSONRenderer(sort_keys=True)
    return structlog.dev.ConsoleRenderer(colors=False)


def _build_processor_formatter() -> logging.Formatter:
    """Return a structlog ``ProcessorFormatter`` for stdlib handlers."""
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_build_processors(),
        processor=_build_final_renderer(),
    )


def _build_formatter(json_mode: bool) -> logging.Formatter:
    """Back-compat shim for legacy stdlib-only tests (e.g. test_json_logging.py).

    New code should use the structlog path via ``setup_logger()`` (which
    wires the ``ProcessorFormatter`` onto the file handler). This
    function is kept so that tests which construct a fresh stdlib logger
    + ``StreamHandler`` + ``setFormatter`` continue to work unchanged.
    """
    if json_mode:
        from pythonjsonlogger.json import JsonFormatter
        return JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "module",
            },
        )
    return logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s',
                             datefmt='%Y-%m-%d %H:%M:%S')


class _NamedPrintLogger(structlog.PrintLogger):
    def __init__(self, file=None) -> None:
        super().__init__(file)
        self.name = "unnamed"


class _NamedPrintLoggerFactory:
    """Print logger factory that stores the logger name so ``add_logger_name`` works."""

    def __init__(self, file=None) -> None:
        self.file = file

    def __call__(self, *args: Any) -> _NamedPrintLogger:
        logger = _NamedPrintLogger(self.file)
        if args:
            first = args[0]
            if isinstance(first, str):
                logger.name = first
            else:
                logger.name = getattr(first, "name", "unnamed")
        return logger


def _ensure_structlog_configured(level: int, file=None) -> None:
    structlog.configure(
        processors=_build_processors() + [_build_final_renderer()],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=_NamedPrintLoggerFactory(file=file),
        cache_logger_on_first_use=True,
    )


def setup_logger(verbose: bool = False) -> logging.Logger:
    """Initialize OPP logging and return the stdlib root logger.

    Idempotent. The structlog configuration is global; calling this
    function more than once is a no-op.

    Two parallel sinks are configured:
    1. ``structlog.PrintLoggerFactory`` writes JSONL to ``log_file``
       (for ``structlog.get_logger("opp.*").info(event, k=v)`` calls)
    2. ``logging.FileHandler`` with ``ProcessorFormatter`` writes JSONL
       to ``log_file`` (for ``logging.getLogger("opp.*").info(msg, extra=...)``
       calls). The ``Log file: ...`` bootstrap line is also emitted via
       this sink.

    When ``verbose=True``, an additional ``StreamHandler`` is attached
    to stderr with a human-readable formatter. This restores the
    ``opp --detect-format -v`` UX where users see the detected format
    in their terminal, in addition to the file-based observability.
    Set up BEFORE the early-return so it works even when the
    module-level ``setup_logger()`` (no args) ran first.
    """
    global _logger_configured
    stdlib_logger = logging.getLogger("opp")

    # Stderr handler for verbose mode — human-readable output to terminal.
    # Set up before the early-return so subsequent calls (e.g. the CLI's
    # ``setup_logger(args.verbose)`` after the module-level import) take effect.
    if verbose and not any(
        getattr(h, "_opp_stderr", False) for h in stdlib_logger.handlers
    ):
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(
            logging.Formatter('[%(levelname)s] %(message)s')
        )
        stderr_handler._opp_stderr = True  # marker so we don't double-add
        stdlib_logger.addHandler(stderr_handler)
        # Bump logger level so INFO messages propagate to stderr
        if stdlib_logger.level > logging.INFO:
            stdlib_logger.setLevel(logging.INFO)

    if _logger_configured:
        return stdlib_logger

    env_level = os.environ.get("OPP_LOG_LEVEL", "").upper()
    if env_level == "DEBUG":
        verbose = True
    level = logging.DEBUG if verbose else logging.INFO

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    log_file = _LOG_DIR / f"opp_{timestamp}.log"

    json_mode = _is_json_mode()
    _ensure_structlog_configured(level, file=open(log_file, "a", encoding="utf-8"))

    stdlib_logger = logging.getLogger("opp")
    stdlib_logger.setLevel(level)
    if not stdlib_logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_build_processor_formatter())
        stdlib_logger.addHandler(file_handler)
        _logger_configured = True
        stdlib_logger.info("Log file: %s", log_file)

    return stdlib_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a stdlib logger for OPP.

    If ``name`` is provided, returns a child logger (``opp.<name>``);
    otherwise returns the root ``opp`` logger. Compatible with the
    pre-migration API (``logger.name`` + ``isinstance(logger, Logger)``).
    """
    if not _logger_configured:
        setup_logger()
    full_name = f"opp.{name}" if name else "opp"
    return logging.getLogger(full_name)


def bind_request_id(request_id: str) -> None:
    """Bind a ``request_id`` to the current context; auto-emitted in JSON output."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_id() -> None:
    """Clear the bound ``request_id`` from the current context."""
    structlog.contextvars.unbind_contextvars("request_id")


logger = setup_logger()
