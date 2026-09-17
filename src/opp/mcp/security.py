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
    # 2026-09-17: 本模块内部不使用该名字，但 MCP 表面需要再导出它
    # （tests/security/*、tests/security/test_path_policy_parity.py 以及下游都以
    # `from opp.mcp.security import PathValidationError` 取用）。写成 `X as X`
    # 这一显式冗余别名，ruff 会识别为有意的再导出而非死导入（F401）。
    PathValidationError as PathValidationError,
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


#: Environment variable that replaces the default extension whitelist
#: (comma-separated, leading dots optional).
_EXTENSIONS_ENV_VAR = "MCP_ALLOWED_EXTENSIONS"


def resolve_allowed_extensions(default: set[str]) -> set[str]:
    """解析 ``MCP_ALLOWED_EXTENSIONS`` 覆盖，未设置或为空时返回 *default*。

    修复（2026-09-17，ADR 0007）：原先只有 ``__init__`` 读环境变量，legacy
    ``validate()`` 直接读类常量 ``ALLOWED_EXTENSIONS``，于是
    ``MCP_ALLOWED_EXTENSIONS`` 在 legacy 路径上静默失效 —— 同一个进程里两条入口
    对同一个文件给出不同答案。抽成单一解析入口后两条路径共用同一份逻辑。

    Args:
        default: 环境变量缺省或为空白时使用的默认白名单。

    Returns:
        生效的扩展名集合，每项都带前导点。
    """
    raw = os.environ.get(_EXTENSIONS_ENV_VAR, "").strip()
    if not raw:
        return default
    return {
        ext if ext.startswith(".") else f".{ext}"
        for ext in (part.strip() for part in raw.split(","))
        if ext
    }


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
        self._allowed_extensions = resolve_allowed_extensions(self.ALLOWED_EXTENSIONS)

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
        # PathValidationError propagates here; @mcp_error_boundary in the
        # caller's tool function catches it and returns a consistent
        # OPP_PATH_DENIED error response (see OPP #52).
        _shared_validate(
            path,
            self.allowed_directories,
            max_file_size_bytes=self.max_file_size_bytes,
            allow_missing=allow_missing,
        )

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

        if path.suffix.lower() not in resolve_allowed_extensions(
            PathValidator.ALLOWED_EXTENSIONS
        ):
            return False, f"Extension '{path.suffix}' not in allowed set"

        if base_dir:
            try:
                resolved.relative_to(base_dir.resolve())
            except ValueError:
                return False, "Path outside allowed directory"

        return True, ""
