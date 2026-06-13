"""Unified path validation — shared across OPP, OL, ORF MCP servers.

Provides a single ``validate_path()`` function that all three MCP servers
can import, ensuring consistent security boundaries.

Covers:
- Path traversal detection (.. components)
- Symlink detection (reject symlinks pointing outside allowed dirs)
- System directory protection (/etc, /usr, /var, /proc, /sys, etc.)
- Blocked executable extensions (.exe, .bat, .sh, .cmd, etc.)
- Directory containment (resolved path must be under an allowed dir)
- Optional file size limits
"""

from pathlib import Path

from opp.utils.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# System directories that should never be accessed
SYSTEM_DIRS: set[str] = {
    "/etc",
    "/usr",
    "/var",
    "/proc",
    "/sys",
    "/System",
    "/Library",
    "/C:/Windows",
    "C:\\Windows",
}

# Blocked file extensions (executables and scripts)
BLOCKED_EXTENSIONS: set[str] = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
    ".vbs",
    ".js",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PathValidationError(ValidationError):
    """Raised when a path fails security validation."""


def validate_path(
    path_str: str,
    allowed_dirs: list[Path],
    max_file_size_bytes: int | None = None,
    allow_missing: bool = False,
) -> Path:
    """Validate a path string is within allowed directories.

    Args:
        path_str: The user-supplied path string.
        allowed_dirs: List of allowed base directories (each will be resolved).
        max_file_size_bytes: If set, reject files larger than this.
        allow_missing: If True, skip the existence check (for output paths).

    Returns:
        Resolved, validated Path.

    Raises:
        PathValidationError: If the path fails any security check.
    """
    # 1. Parse the path
    try:
        p = Path(path_str)
    except (ValueError, OSError) as e:
        raise PathValidationError(f"Invalid path format: {e}") from e

    # 2. Check for path traversal attempts
    if ".." in p.parts:
        raise PathValidationError(
            f"Path traversal detected (.. components are not allowed): {path_str}"
        )

    # 3. Resolve the path (follows symlinks)
    try:
        resolved = p.resolve()
    except (ValueError, OSError) as e:
        raise PathValidationError(f"Cannot resolve path: {e}") from e

    # 4. Check if path points to a system directory
    for sys_dir in SYSTEM_DIRS:
        sys_path = Path(sys_dir)
        resolved_parts = resolved.parts
        sys_parts = sys_path.parts
        if len(resolved_parts) >= len(sys_parts):
            if all(a == b for a, b in zip(resolved_parts[: len(sys_parts)], sys_parts)):
                raise PathValidationError(
                    f"Access to system directory not allowed: {sys_dir}"
                )

    # 5. Resolve allowed directories
    resolved_allowed = [Path(d).resolve() for d in allowed_dirs]

    # 6. Check if resolved path is within allowed directories
    is_allowed = False
    for allowed in resolved_allowed:
        try:
            resolved.relative_to(allowed)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        raise PathValidationError(
            f"Path not in allowed directories: {path_str}"
        )

    # 7. Check if path is a symlink pointing outside allowed directories
    if p.is_symlink():
        try:
            link_target = p.resolve()
            link_allowed = False
            for allowed in resolved_allowed:
                try:
                    link_target.relative_to(allowed)
                    link_allowed = True
                    break
                except ValueError:
                    continue
            if not link_allowed:
                raise PathValidationError(
                    "Symlink points outside allowed directories"
                )
        except (ValueError, OSError) as e:
            raise PathValidationError(
                f"Symlink target is not accessible: {e}"
            ) from e

    # 8. Check blocked extensions
    if p.suffix.lower() in BLOCKED_EXTENSIONS:
        raise PathValidationError(
            f"File extension '{p.suffix}' is blocked"
        )

    # 9. Existence check
    if not resolved.exists():
        if allow_missing:
            return resolved
        raise PathValidationError("File does not exist")

    # 10. Must be a file (not directory)
    if not resolved.is_file():
        raise PathValidationError("Path must be a file, not a directory")

    # 11. File size check
    if max_file_size_bytes is not None:
        try:
            file_size = resolved.stat().st_size
            if file_size > max_file_size_bytes:
                raise PathValidationError(
                    f"File size ({file_size} bytes) exceeds limit "
                    f"of {max_file_size_bytes} bytes"
                )
        except OSError as e:
            raise PathValidationError(
                f"Cannot access file to check size: {e}"
            ) from e

    return resolved


def validate_path_safe(
    path_str: str,
    allowed_dirs: list[Path],
    max_file_size_bytes: int | None = None,
    allow_missing: bool = False,
) -> tuple[bool, str, Path | None]:
    """Like validate_path() but returns (success, error_msg, path) tuple.

    This is the non-raising variant for callers that prefer a return-value
    pattern over exception handling.

    Returns:
        (True, "", resolved_path) on success, (False, error_msg, None) on failure.
    """
    try:
        resolved = validate_path(
            path_str,
            allowed_dirs,
            max_file_size_bytes=max_file_size_bytes,
            allow_missing=allow_missing,
        )
        return True, "", resolved
    except PathValidationError as e:
        return False, str(e), None
