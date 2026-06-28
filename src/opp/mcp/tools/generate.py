"""Generate markdown and XLIFF tools.

These two tools convert an already-extracted document into Markdown text or
XLIFF 1.2/2.0 format for downstream translation workflows.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from opp.mcp._errors import mcp_error_boundary, McpError
from opp.mcp.auth import check_auth
from opp.mcp import common as _c
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def generate_xliff(
    file_path: str,
    source_lang: str = "zh",
    target_lang: str = "en",
    output_path: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Convert a document to XLIFF format for translation workflows.

    Requires source and target language codes. Optionally accepts an
    explicit ``output_path``; if omitted, writes to a generated path
    next to the input file.
    """
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    request_id = str(uuid.uuid4())
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

    if output_path is None:
        input_p = Path(file_path)
        output_path = str(
            input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".xlf")
        )

    output_validation = _c._validator.validate_path(output_path, allow_missing=True)
    if not output_validation.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=f"Output path validation failed: {output_validation.error}",
        )

    try:
        result = _c._pipeline.process_file(Path(file_path))

        if result.extraction_result is None:
            raise McpError(
                code="OPP_INTERNAL_ERROR",
                message="No extraction result available",
            )

        xliff_output_path = _c._pipeline.generate_xliff(
            result.extraction_result,
            Path(output_path),
            source_lang,
            target_lang,
            request_id=request_id,
        )

        with open(xliff_output_path, "r", encoding="utf-8") as f:
            xliff_content = f.read()

        units_count = xliff_content.count("<trans-unit") if xliff_content else 0

        return {
            "success": True,
            "content": {
                "xliff_content": xliff_content,
                "output_path": str(xliff_output_path),
                "units_count": units_count,
            },
        }

    except McpError:
        raise
    except ValueError as e:
        raise McpError(code="OPP_INVALID_INPUT", message=str(e))
    except Exception as e:
        raise McpError(
            code="OPP_INTERNAL_ERROR",
            message=f"XLIFF generation failed: {str(e)}",
        )


@mcp_error_boundary
async def generate_markdown(
    file_path: str,
    output_path: str | None = None,
    style_mapping: dict[str, int] | None = None,
    embed_images: bool = True,
    auth_token: str | None = None,
) -> dict:
    """Convert a document to Markdown format.

    Optionally accepts an explicit ``output_path``, ``style_mapping``
    (heading level overrides per style name), and ``embed_images``
    (base64-inline images into the output).
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

    input_p = Path(file_path)

    if output_path is None:
        output_path = str(
            input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".md")
        )
    else:
        output_validation = _c._validator.validate_path(output_path, allow_missing=True)
        if not output_validation.success:
            raise McpError(
                code="OPP_PATH_DENIED",
                message=f"Output path validation failed: {output_validation.error}",
            )

    try:
        result = _c._pipeline.process_file(input_p)

        if result.extraction_result is None:
            raise McpError(
                code="OPP_INTERNAL_ERROR",
                message="No extraction result available",
            )

        md_output_path = _c._pipeline.generate_markdown(
            result.extraction_result,
            Path(output_path),
            style_mapping=style_mapping,
            embed_images=embed_images,
        )

        with open(md_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        images_count = markdown_content.count("![]")
        images_dir = str(
            Path(output_path).with_suffix("")
            / f"{Path(output_path).stem}_images"
        )

        return {
            "success": True,
            "content": {
                "markdown_content": markdown_content,
                "output_path": str(md_output_path),
                "images_dir": images_dir,
                "images_count": images_count,
            },
        }

    except McpError:
        raise
    except Exception as e:
        raise McpError(
            code="OPP_INTERNAL_ERROR",
            message=f"Markdown generation failed: {str(e)}",
        )
