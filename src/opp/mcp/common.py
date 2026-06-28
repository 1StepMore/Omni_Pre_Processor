"""Shared state and helper functions for OPP MCP server tools.

This module holds the mutable module-level state (``_config``, ``_validator``,
``_pipeline``, ``_serializer``, ``_tempfiles``) and utility functions that are
shared across the tool modules in ``opp.mcp.tools``. It also owns the shutdown
cleanup lifecycle (tempfiles, resource dir, signal handlers).
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import signal as _signal
import tempfile
from pathlib import Path
from typing import Any

from opp.mcp.config import MCPConfig, load_config
from opp.mcp.security import PathValidator
from opp.mcp.serializers import ExtractionResultSerializer
from opp.pipeline import OPPPipeline


logger = logging.getLogger("opp_mcp.server")


# ─────────────────────────────────────────────────────────────────────
# Shared mutable state — initialized by _init_server(), consumed by tools
# ─────────────────────────────────────────────────────────────────────

_config: MCPConfig | None = None
_validator: PathValidator | None = None
_pipeline: OPPPipeline | None = None
_serializer: ExtractionResultSerializer | None = None
_tempfiles: set[Path] = set()


# ─────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────

def _init_server(config: MCPConfig) -> None:
    """Initialize the shared server state from a config object.

    Sets up the PathValidator, OPPPipeline, and ExtractionResultSerializer
    used by all tool functions. Called once at server startup.
    """
    global _config, _validator, _pipeline, _serializer

    _config = config
    _validator = PathValidator(
        allowed_directories=config.allowed_directories,
        max_file_size_bytes=config.max_file_size_bytes,
    )
    _pipeline = OPPPipeline(resource_storage_dir=config.resource_storage_dir)
    _serializer = ExtractionResultSerializer()


# ─────────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────────

def _suggest_pipeline(format_type: str) -> str:
    """Map format_type to recommended pipeline.

    Returns one of: ``'md_only'``, ``'xliff_only'``, ``'both'``, ``'neither'``.
    """
    fmt = format_type.lower() if format_type else ""
    if fmt == "pdf":
        return "md_only"
    if fmt in ("docx", "pptx", "epub"):
        return "both"
    if fmt == "unknown":
        return "neither"
    return "md_only"


def _safe_unlink(path: Path) -> bool:
    """C3 fix: resolve+revalidate path before unlink, then refuse to follow
    symlinks. Returns True if a file was deleted, False otherwise.
    """
    if _validator is None:
        return False
    try:
        resolved = path.resolve()
    except (ValueError, OSError):
        return False
    if path.is_symlink():
        return False
    result = _validator.validate_path(str(resolved), allow_missing=True)
    if not result.success:
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False


def _safe_rmtree(path: Path) -> None:
    """Recursively remove a directory tree. Ignores errors."""
    shutil.rmtree(path, ignore_errors=True)


def _safe_temp_output(suffix: str, parent: Path) -> Path:
    """Create a tempfile inside the resolved parent dir (which must be in an
    allowed dir). Returns the Path. C3 fix: intermediate outputs go in
    tempfiles, never at the input file's with_suffix location.
    OPP#10: registers the created file in ``_tempfiles`` for shutdown cleanup.
    """
    parent_resolved = parent.resolve()
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="opp_mcp_", dir=str(parent_resolved))
    os.close(fd)
    p = Path(name)
    _tempfiles.add(p)
    return p


# ─────────────────────────────────────────────────────────────────────
# Shutdown / cleanup
# ─────────────────────────────────────────────────────────────────────

def _cleanup_tempfiles() -> int:
    """Unlink all tracked temp files and directories. Returns count removed."""
    removed = 0
    for p in list(_tempfiles):
        try:
            if p.exists() and not p.is_symlink():
                if p.is_dir():
                    _safe_rmtree(p)
                else:
                    p.unlink()
                removed += 1
        except OSError as e:
            logger.debug(f"Failed to unlink temp file {p}: {e}")
        finally:
            _tempfiles.discard(p)
    if removed:
        logger.debug(f"OPP#10 cleanup: unlinked {removed} temp file(s)")
    return removed


def _cleanup_resource_dir() -> int:
    """Recursively remove the resource_storage_dir. Returns count of files
    removed. OPP#10: only called when cleanup_on_shutdown=True.
    """
    if _config is None or _config.cleanup_on_shutdown is False:
        return 0
    resource_dir = _config.resource_storage_dir
    if not resource_dir.exists():
        return 0
    resolved = str(resource_dir.resolve())
    if resolved in ("/", str(Path.cwd().resolve())):
        logger.error(
            f"OPP#10 cleanup refused: resource_storage_dir={resource_dir} "
            f"resolves to a system path, refusing to rmtree"
        )
        return 0
    count = sum(1 for _ in resource_dir.rglob("*") if _.is_file())
    try:
        shutil.rmtree(resource_dir)
        logger.info(
            f"OPP#10 cleanup: removed resource dir {resource_dir} "
            f"({count} file(s))"
        )
        return count
    except OSError as e:
        logger.error(f"OPP#10 cleanup failed to rmtree {resource_dir}: {e}")
        return 0


def _shutdown_cleanup() -> None:
    """Run on atexit / signal. Always cleans temp files; cleans resource
    dir only if ``cleanup_on_shutdown=True``.
    """
    n_temp = 0
    n_res = 0
    try:
        n_temp = _cleanup_tempfiles()
    except Exception as e:
        logger.error(f"OPP#10 temp cleanup failed: {e}")
    try:
        n_res = _cleanup_resource_dir()
    except Exception as e:
        logger.error(f"OPP#10 resource cleanup failed: {e}")
    if n_temp or n_res:
        logger.info(
            f"OPP#10 shutdown cleanup: {n_temp} temp file(s), "
            f"{n_res} resource file(s)"
        )


def _signal_handler(signum: int, frame: Any) -> None:
    """Signal handler for SIGTERM/SIGINT.

    Runs ``_shutdown_cleanup()`` then delegates to the default handler
    for clean process exit.
    """
    logger.info(f"OPP#10: received signal {signum}, running cleanup")
    _shutdown_cleanup()
    _signal.default_int_handler(signum, frame)


# Register shutdown cleanup on interpreter exit
atexit.register(_shutdown_cleanup)
