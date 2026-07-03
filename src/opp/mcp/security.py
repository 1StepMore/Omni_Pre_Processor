"""Path validation with directory allowlist and file size limits.

Delegates core validation checks to ``opp.utils.security.validate_path()``
(the shared unified validator) while adding OPP/MCP-specific features:
- Extension whitelist (``ALLOWED_EXTENSIONS``)
- ``ValidationResult`` dataclass API for structured success/error returns
"""

import os
from dataclasses import dataclass
from pathlib import Path

from opp.utils.security import (
    BLOCKED_EXTENSIONS,
    SYSTEM_DIRS,
    PathValidationError,
    validate_path as _shared_validate,
)

# Re-export constants for backward compatibility
__all__ = [
    "SYSTEM_DIRS",
    "BLOCKED_EXTENSIONS",
    "ValidationResult",
    "PathValidator",
]


@dataclass
class ValidationResult:
    """Result of path validation.

    Attributes:
        success: True if path passed all validation checks.
        error: Error message if validation failed, None otherwise.
        resolved_path: The resolved Path object if successful, None otherwise.
    """

    success: bool
    error: str | None = None
    resolved_path: Path | None = None


class PathValidator:
    """Validates file paths against security rules.

    Validates that:
    - Path doesn't contain traversal components (..)
    - Path resolves to an allowed directory
    - Path is not a symlink pointing outside allowed directories
    - Path doesn't target system directories
    - File has allowed extension (document whitelist)
    - File extension is not blocked (executable blacklist)
    - File size is within limit
    - File exists and is accessible

    Args:
        allowed_directories: List of root directories that are allowed to access.
        max_file_size_bytes: Maximum allowed file size in bytes (default: 100MB).
    """

    # Document format extensions allowed through MCP
    ALLOWED_EXTENSIONS: set[str] = {
        ".md", ".docx", ".pptx", ".pdf", ".xliff", ".xlf", ".xml",
        ".html", ".odt", ".epub", ".zip", ".txt",
        ".xlsx", ".csv", ".json", ".eml",
    }

    def __init__(
        self,
        allowed_directories: list[Path],
        max_file_size_bytes: int = 100_000_000,
    ):
        self.allowed_directories = [Path(d).resolve() for d in allowed_directories]
        self.max_file_size_bytes = max_file_size_bytes
        env_ext = os.environ.get("MCP_ALLOWED_EXTENSIONS")
        if env_ext:
            self._allowed_extensions = {
                e.strip() if e.strip().startswith(".") else f".{e.strip()}"
                for e in env_ext.split(",")
                if e.strip()
            }
        else:
            self._allowed_extensions = self.ALLOWED_EXTENSIONS

    def validate_path(
        self, path: str, allow_missing: bool = False
    ) -> ValidationResult:
        """Validate a file path against security rules.

        Args:
            path: The path string to validate.
            allow_missing: If True, skip the existence check (for output paths).
                          If False (default), file must exist and be readable.

        Returns:
            ValidationResult with success=True if valid, or success=False with error message.
        """
        # --- Phase 1: Core shared validation (traversal, symlink, system dirs,
        #              blocked extensions, directory containment, size) ---
        try:
            _shared_validate(
                path,
                self.allowed_directories,
                max_file_size_bytes=self.max_file_size_bytes,
                allow_missing=allow_missing,
            )
        except PathValidationError as e:
            return ValidationResult(success=False, error=str(e))

        # Phase 1 succeeded — get the resolved path
        try:
            p = Path(path)
            resolved = p.resolve()
        except (ValueError, OSError) as e:
            return ValidationResult(success=False, error=f"Invalid path: {e}")

        if not resolved.exists():
            if allow_missing:
                return ValidationResult(success=True, resolved_path=resolved)
            return ValidationResult(success=False, error="File does not exist")

        # --- Phase 2: Extension whitelist (OPP/ORF specific) ---
        if p.suffix.lower() not in self._allowed_extensions:
            return ValidationResult(
                success=False,
                error=f"Extension '{p.suffix}' not in allowed set",
            )

        return ValidationResult(success=True, resolved_path=resolved)

    @staticmethod
    def validate(
        input_path: str, base_dir: Path | None = None
    ) -> tuple[bool, str]:
        """[Legacy] Static path validation for backward compatibility.

        This is a simplified wrapper that checks path traversal and allowed
        extensions only. For full validation (directory containment, system
        dir blocking, symlink checks, file size limits), use the instance
        method ``validate_path()`` via ``PathValidator(allowed_directories=...).validate_path(path)``.

        Returns:
            (is_valid, error_message) tuple matching the original API.
        """
        path = Path(input_path)

        # Check for directory traversal
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False, "Invalid path"

        if ".." in path.parts:
            return False, "Path traversal not allowed"

        if path.suffix.lower() not in PathValidator.ALLOWED_EXTENSIONS:
            return False, f"Extension '{path.suffix}' not in allowed set"

        if base_dir:
            try:
                resolved.relative_to(base_dir.resolve())
            except ValueError:
                return False, "Path outside allowed directory"

        return True, ""
