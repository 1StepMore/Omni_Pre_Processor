"""Detect format tool — identify file format via magic bytes."""

from __future__ import annotations

import logging
from pathlib import Path

from opp.detector import detect_format
from opp.mcp._errors import mcp_error_boundary, McpError

logger = logging.getLogger(__name__)
from opp.mcp.auth import check_auth
from opp.mcp import common as _c
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def detect_format_tool(
    file_path: str, auth_token: str | None = None
) -> dict:
    """Identify the file format using magic-bytes detection.

    Returns the format name (e.g. ``"DOCX"``, ``"PDF"``) and a confidence
    score in ``[0.0, 1.0]``. Works regardless of file extension.
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
    if _c._validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _c._validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    try:
        fmt, confidence = detect_format(Path(file_path))
        return {
            "success": True,
            "content": {"format": fmt.value, "confidence": confidence},
        }
    except Exception as e:
        logger.debug("Format detection failed: %s", e)
        raise McpError(
            code="OPP_INTERNAL_ERROR",
            message=f"Format detection failed: {str(e)}",
        )
