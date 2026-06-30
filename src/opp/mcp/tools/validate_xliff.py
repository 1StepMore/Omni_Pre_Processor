"""validate_xliff MCP tool for OPP.

Validate an XLIFF 1.2 file against the OASIS XSD schema and the
trans-unit content rules (non-empty source, unique IDs, valid lang codes).

Accepts either:
- ``xliff_content`` (inline string) — preferred for agent workflows
- ``file_path`` (path to file) — for batch tools

If both are provided, ``xliff_content`` takes precedence.
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

    if not xliff_content and not file_path:
        return {
            "success": False,
            "error": {
                "code": "OPP_INVALID_INPUT",
                "message": "Either xliff_content or file_path is required.",
            },
            "error_code": "OPP_INVALID_INPUT",
        }

    if xliff_content:
        raw_bytes = xliff_content.encode("utf-8")
    else:
        if _c._validator is None:
            raise McpError(
                code="OPP_INTERNAL_ERROR",
                message="Server not initialized.",
            )
        vresult = _c._validator.validate_path(file_path)
        if not vresult.success:
            raise McpError(
                code="OPP_PATH_DENIED",
                message=vresult.error or "Path validation failed",
            )
        path = Path(file_path)
        if not path.is_file():
            return {
                "success": False,
                "error": {
                    "code": "OPP_INVALID_INPUT",
                    "message": f"File not found: {file_path}",
                },
                "error_code": "OPP_INVALID_INPUT",
            }
        raw_bytes = path.read_bytes()

    if not raw_bytes:
        return {
            "success": False,
            "error": {
                "code": "OPP_INVALID_INPUT",
                "message": "XLIFF content is empty.",
            },
            "error_code": "OPP_INVALID_INPUT",
        }

    from opp.xliff.validator import XLIFFValidator

    validator = XLIFFValidator()
    schema_valid, schema_errors = validator.validate_schema(raw_bytes)
    tu_valid, tu_warnings, tu_errors = validator.validate_trans_units(raw_bytes)
    is_valid = bool(schema_valid) and bool(tu_valid)

    return {
        "success": True,
        "content": {
            "is_valid": is_valid,
            "schema_valid": bool(schema_valid),
            "trans_units_valid": bool(tu_valid),
            "schema_errors": list(schema_errors or []),
            "trans_unit_errors": list(tu_errors or []),
            "trans_unit_warnings": list(tu_warnings or []),
            "error_count": len(schema_errors or []) + len(tu_errors or []),
            "warning_count": len(tu_warnings or []),
        },
    }
