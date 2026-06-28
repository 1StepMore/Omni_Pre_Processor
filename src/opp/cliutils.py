"""Shared utilities for OPP CLI — cache, env loading, path helpers.

Extracted from ``cli.py`` during the Task 3.7 split. All functions are
re-exported from ``opp.cli`` for backward compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
from pathlib import Path

from opp.logger import get_logger
from opp.utils.cache import cache_root


# ========== A6: Content-addressed cache (~/.omni_cache/opp/) ==========
# Re-runs of the same input+config skip the expensive extraction and just
# copy the cached .xlf to the output dir. The cache root can be overridden
# with the OMNI_CACHE_DIR env var (used by tests). Mode 0o700 protects any
# sensitive content (e.g., a translated DOCX that contains private info).
# CACHE_DIR is computed lazily so the OMNI_CACHE_DIR override works even
# when tests set the env var after the module is imported.
CACHE_DIR_NAME = "opp"


def _cache_root() -> Path:
    """Return the OPP cache root, delegating to the shared utility."""
    return cache_root(CACHE_DIR_NAME)


def _cache_key(input_path: Path, config: dict) -> str:
    """Return sha256(input_bytes + repr(sorted(config.items()))).

    Uses chunked reading (8 KB blocks) instead of loading the entire file
    into memory, preventing OOM on large files.
    """
    h = hashlib.sha256()
    with open(input_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    h.update(repr(sorted(config.items())).encode())
    return h.hexdigest()


def _relevant_config_for_cache(args: argparse.Namespace) -> dict:
    """Build the config dict that affects the cache key for OPP.

    Only the user-supplied ``--config`` file is hashed; CLI flags like
    --source-lang/--target-lang are NOT in the cache key because they are
    typically derived from the config file (and including them would
    invalidate the cache for any CLI override of an unchanged config).
    """
    if args.config and args.config.exists():
        return {
            "config_file_sha256": hashlib.sha256(
                args.config.read_bytes()
            ).hexdigest()
        }
    return {}


def _check_cache(file_path: Path, args: argparse.Namespace, output_dir: Path) -> bool:
    """If cached, copy ``<stem>.xlf`` to ``output_dir`` and return True."""
    if getattr(args, "no_cache", False):
        return False
    key = _cache_key(file_path, _relevant_config_for_cache(args))
    cache_file = _cache_root() / f"{key}.xlf"
    if cache_file.exists():
        target = output_dir / f"{file_path.stem}.xlf"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(cache_file, target)
        get_logger().info(f"Cache hit: {cache_file} -> {target}")
        return True
    return False


def _write_cache(file_path: Path, args: argparse.Namespace, output_dir: Path) -> None:
    """Copy the produced .xlf into the cache for next run."""
    if getattr(args, "no_cache", False):
        return
    output_file = output_dir / f"{file_path.stem}.xlf"
    if not output_file.exists():
        return
    key = _cache_key(file_path, _relevant_config_for_cache(args))
    cache_file = _cache_root() / f"{key}.xlf"
    cache_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy(output_file, cache_file)
    get_logger().debug(f"Cache miss: wrote {cache_file}")


def _clear_opp_cache() -> int:
    """Remove all cached OPP files. Returns the number of files removed."""
    root = _cache_root()
    if not root or root == Path("/") or root == Path.home() or root == Path.cwd():
        get_logger().error("Refusing to clear cache: %s is a system directory", root)
        return 0
    if not root.exists():
        return 0
    count = sum(1 for _ in root.iterdir())
    shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return count


# ========== Environment loading ==========


def _load_env_for_opp() -> None:
    """Load .env file for OPP CLI commands.

    Search order:
      1. $OPP_DOTENV env var (explicit override)
      2. ./.env (current working directory)
      3. Walk up parent directories looking for .env
      4. ~/.config/opp/.env (user-level fallback)

    If no .env is found, the function returns silently.
    """
    search_paths: list[Path] = []
    explicit = os.environ.get("OPP_DOTENV")
    if explicit:
        search_paths.append(Path(explicit))
    search_paths.append(Path.cwd() / ".env")
    for parent in Path.cwd().resolve().parents:
        candidate = parent / ".env"
        if candidate not in search_paths:
            search_paths.append(candidate)
    search_paths.append(Path.home() / ".config" / "opp" / ".env")

    for env_path in search_paths:
        if env_path.exists() and env_path.is_file():
            _load_dotenv_for_opp(env_path)
            return


def _load_dotenv_for_opp(env_path: Path) -> None:
    """Parse and export .env file without blocking on missing keys."""
    try:
        content = env_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            # Strip optional 'export' prefix (common shell convention)
            line = line.removeprefix("export ").lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
    except Exception as exc:
        get_logger().warning("Failed to load .env file %s: %s", env_path, exc)


# ========== File helpers ==========


def get_supported_extensions() -> list[str]:
    return ['.docx', '.pptx', '.pdf', '.html', '.epub', '.eml', '.msg', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']


def expand_directories(paths: list[Path]) -> list[Path]:
    files = []
    for path in paths:
        if path.is_dir():
            supported_exts = get_supported_extensions()
            for ext in supported_exts:
                for f in path.rglob(f'*{ext}'):
                    if not f.name.startswith('.') and f.is_file():
                        files.append(f)
        elif path.is_file():
            files.append(path)
    return files


def _detect_format_from_extension(path: Path) -> str:
    """Detect format type from file extension."""
    ext = path.suffix.lower()
    format_map = {
        ".docx": "DOCX", ".pptx": "PPTX", ".pdf": "PDF",
        ".xlsx": "XLSX", ".html": "HTML", ".xml": "XML",
        ".json": "JSON", ".csv": "CSV", ".epub": "EPUB",
        ".eml": "EML", ".msg": "MSG", ".md": "MARKDOWN",
        ".xlf": "XLIFF", ".xliff": "XLIFF",
    }
    return format_map.get(ext, "UNKNOWN")


def _compute_file_md5(path: Path) -> str:
    """Compute MD5 hash of file using chunked reading."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _count_xliff_units(xliff_path: Path) -> int:
    """Count trans-unit elements in XLIFF file."""
    content = xliff_path.read_text(encoding="utf-8")
    return len(re.findall(r'<trans-unit[^>]*>', content))


def get_opp_version() -> str:
    """Return OPP version string."""
    from opp import __version__
    return __version__
