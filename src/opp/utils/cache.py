"""Shared cache-root utility for Omni Suite modules (OPP / OL / ORF).

Each module (opp, ol, orf) creates its own subdirectory under the cache
root.  The root itself is configurable via the ``OMNI_CACHE_DIR`` env var
(default: ``~/.omni_cache``).  Directories are created with mode 0o700 to
protect any sensitive content that may be cached.
"""

from __future__ import annotations

import os
from pathlib import Path


def cache_root(module_name: str) -> Path:
    """Return (and create) the per-module cache directory.

    Parameters
    ----------
    module_name:
        Short name for the module (e.g. ``"opp"``, ``"ol"``, ``"orf"``).

    Returns
    -------
    Path
        The absolute path to the directory, guaranteed to exist after the
        call.
    """
    root = Path(
        os.environ.get("OMNI_CACHE_DIR", str(Path.home() / ".omni_cache"))
    )
    path = root / module_name
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path
