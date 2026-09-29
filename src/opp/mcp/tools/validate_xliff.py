"""validate_xliff MCP tool for OPP.

Validate an XLIFF 1.2 file against the OASIS XSD schema and the
trans-unit content rules (non-empty source, unique IDs, valid lang codes).

Accepts either:
- ``xliff_content`` (inline string) — preferred for agent workflows
- ``file_path`` / ``xliff_path`` (path to file) — ``xliff_path`` is the
  pipeline/ORF naming and is an accepted alias for ``file_path``

If ``xliff_content`` is provided it takes precedence over both path
parameters. Supplying both ``file_path`` and ``xliff_path`` is rejected
as ambiguous (``OPP_INVALID_INPUT``).
"""
from __future__ import annotations

import logging
from pathlib import Path

from opp.mcp import common as _c
from opp.mcp._errors import McpError, mcp_error_boundary
from opp.mcp.auth import check_auth
from opp.mcp.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)


@mcp_error_boundary
async def validate_xliff(
    xliff_content: str | None = None,
    file_path: str | None = None,
    xliff_path: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Validate an XLIFF 1.2 file.

    Returns a dict with:
        success (bool): True if validation completed (even with errors).
        content.is_valid (bool): True if the file is fully valid.
        content.schema_valid (bool): True if XSD schema validates.
        content.trans_units_valid (bool): True if trans-unit rules pass.
        content.schema_errors (list[str]): XSD-level errors.
        content.trans_unit_errors (list[str]): trans-unit rule errors.
        content.trans_unit_warnings (list[str]): warnings.
        content.errors (list[dict]): structured errors with code/line/column.
        content.error_count (int): total error count.
        content.warning_count (int): total warning count.
    """
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(
            code="AUTH_FAILED",
            message="Authentication failed: auth_token is missing or incorrect.",
        )

    if not xliff_content and file_path and xliff_path:
        raise McpError(
            code="OPP_INVALID_INPUT",
            message="Provide only one of file_path / xliff_path.",
        )

    resolved_path = file_path or xliff_path

    if not xliff_content and not resolved_path:
        raise McpError(
            code="OPP_INVALID_INPUT",
            message="Either xliff_content or file_path is required.",
        )

    if xliff_content:
        raw_bytes = xliff_content.encode("utf-8")
    else:
        if _c._validator is None:
            raise McpError(
                code="OPP_INTERNAL_ERROR",
                message="Server not initialized.",
            )
        vresult = _c._validator.validate_path(resolved_path)
        if not vresult.success:
            raise McpError(
                code="OPP_PATH_DENIED",
                message=vresult.error or "Path validation failed",
            )
        path = Path(resolved_path)
        if not path.is_file():
            raise McpError(
                code="OPP_INVALID_INPUT",
                message=f"File not found: {resolved_path}",
            )
        raw_bytes = path.read_bytes()

    if not raw_bytes:
        raise McpError(
            code="OPP_INVALID_INPUT",
            message="XLIFF content is empty.",
        )

    from opp.xliff.validator import XLIFFValidator

    validator = XLIFFValidator()
    result = validator.validate(raw_bytes)

    return {
        "success": True,
        "content": {
            "is_valid": result["is_valid"],
            "schema_valid": result["schema_valid"],
            "trans_units_valid": result["trans_units_valid"],
            "schema_errors": result["schema_errors"],
            "trans_unit_errors": result["trans_unit_errors"],
            "trans_unit_warnings": result["trans_unit_warnings"],
            "errors": result["errors"],
            "error_count": result["error_count"],
            "warning_count": result["warning_count"],
        },
    }
