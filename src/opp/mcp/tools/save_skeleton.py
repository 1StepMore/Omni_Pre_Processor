"""Save skeleton tool — save skeleton ZIP from extracted document.

The skeleton preserves the original DOCX/PPTX ZIP structure and is required
by ORF's ``apply_xliff`` for XLIFF->DOCX/PPTX backfill.
"""

from __future__ import annotations

import logging
from pathlib import Path

from opp.mcp._errors import mcp_error_boundary, McpError

logger = logging.getLogger(__name__)
from opp.mcp.auth import check_auth
from opp.mcp import common as _c
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def save_skeleton(
    file_path: str,
    base_name: str = "document",
    output_dir: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Save skeleton ZIP file from extracted document.

    Runs OPP extraction (``process_file``), then saves the skeleton via
    ``OPPPipeline.save_skeleton``. Returns the skeleton path. The skeleton
    is required by ORF's ``apply_xliff`` as the ``input_file`` arg.
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

    output_path = Path(output_dir) if output_dir else Path(file_path).parent
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        result = _c._pipeline.process_file(Path(file_path))
        if result.extraction_result is None:
            raise McpError(code="OPP_INTERNAL_ERROR", message="No extraction result")

        skeleton_path = _c._pipeline.save_skeleton(
            result.extraction_result, base_name, output_path,
        )
        return {
            "success": True,
            "content": {
                "skeleton_path": str(skeleton_path) if skeleton_path else None,
            },
        }
    except McpError:
        raise
    except Exception as e:
        logger.debug("Skeleton save failed: %s", e)
        raise McpError(
            code="OPP_INTERNAL_ERROR",
            message=f"Skeleton save failed: {str(e)}",
        )
