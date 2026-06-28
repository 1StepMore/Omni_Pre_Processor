"""Batch extract tool — process multiple files in one request."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from opp.mcp._errors import mcp_error_boundary, validate_file_paths, McpError

logger = logging.getLogger(__name__)
from opp.mcp.auth import check_auth
from opp.mcp import common as _c
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def batch_extract(
    file_paths: list[str],
    output_formats: list[str] | str | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
    auth_token: str | None = None,
) -> dict:
    """Process multiple files in one request.

    Validates all paths upfront, then extracts each file sequentially.
    Returns per-file extraction results plus aggregate counts and total
    duration.

    Args:
        file_paths: List of absolute file paths to extract.
        output_formats: ``"md"``, ``"xlf"``, ``"both"``, or a list.
        source_lang: Source language code (default ``"zh"``).
        target_lang: Target language code (default ``"en"``).
        auth_token: Shared-secret auth token.

    Returns:
        A dict with ``success``, ``results`` (per-file), ``successful``,
        ``failed``, and ``total_duration_ms``.
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
    request_id = str(uuid.uuid4())

    if output_formats is None:
        output_formats = ["md"]

    if isinstance(output_formats, str):
        output_formats = [output_formats]

    valid_formats = {"md", "xlf", "both"}
    for fmt in output_formats:
        if fmt not in valid_formats:
            raise McpError(
                code="OPP_INVALID_INPUT",
                message=f"Invalid output format: '{fmt}'. Valid values are: {sorted(valid_formats)}",
            )

    if _c._validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validate_file_paths(file_paths)

    validation_errors = []
    for file_path in file_paths:
        validation_result = _c._validator.validate_path(file_path)
        if not validation_result.success:
            validation_errors.append({
                "file_path": file_path,
                "error": validation_result.error or "Path validation failed",
            })

    if validation_errors:
        raise McpError(
            code="OPP_PATH_DENIED",
            message="Path validation failed for one or more files",
        )

    results = []
    successful = 0
    failed = 0
    start_time = time.time()

    for file_path in file_paths:
        try:
            result = _c._pipeline.process_file(Path(file_path))
            serialized = _c._serializer.serialize(result, include_base64=True)

            # -- MD output (per file) ---------------------------------
            if "md" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    md_output_path = _c._safe_temp_output(
                        ".md", Path(file_path).parent
                    )
                    try:
                        _c._pipeline.generate_markdown(
                            result.extraction_result, md_output_path
                        )
                        if md_output_path.exists():
                            with open(md_output_path, "r", encoding="utf-8") as f:
                                serialized["md_content"] = f.read()
                        images_dir = (
                            md_output_path.parent
                            / f"{Path(file_path).stem}_images"
                        )
                        if images_dir.exists():
                            _c._tempfiles.add(images_dir)
                            serialized["images_dir"] = str(images_dir)
                    except Exception as e:
                        logger.debug("Markdown generation failed in batch_extract: %s", e)
                        serialized.setdefault("warnings", []).append(
                            f"Markdown generation failed: {str(e)}"
                        )
                    finally:
                        _c._safe_unlink(md_output_path)

            # -- XLIFF output (per file) --------------------------------
            if "xlf" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    xliff_output_path = _c._safe_temp_output(
                        ".xlf", Path(file_path).parent
                    )
                    try:
                        _c._pipeline.generate_xliff(
                            result.extraction_result,
                            xliff_output_path,
                            source_lang,
                            target_lang,
                            request_id=request_id,
                        )
                        if xliff_output_path.exists():
                            with open(
                                xliff_output_path, "r", encoding="utf-8"
                            ) as f:
                                xliff_content = f.read()
                            serialized["xliff_content"] = xliff_content
                            serialized["xliff_units_count"] = (
                                xliff_content.count("<trans-unit")
                                if xliff_content
                                else 0
                            )
                    except ValueError as e:
                        serialized["success"] = False
                        serialized["error"] = str(e)
                        serialized["xliff_error"] = str(e)
                    except Exception as e:
                        logger.debug("XLIFF generation failed in batch_extract: %s", e)
                        serialized.setdefault("warnings", []).append(
                            f"XLIFF generation failed: {str(e)}"
                        )
                    finally:
                        if not _c._config.output_dir:
                            _c._safe_unlink(xliff_output_path)

            results.append({
                "file_path": file_path,
                **serialized,
            })
            successful += 1
        except Exception as e:
            logger.debug("Extraction failed in batch_extract for %s: %s", file_path, e)
            results.append({
                "file_path": file_path,
                "success": False,
                "error": f"Extraction failed: {str(e)}",
            })
            failed += 1

    total_duration_ms = (time.time() - start_time) * 1000

    return {
        "success": True,
        "results": results,
        "successful": successful,
        "failed": failed,
        "total_duration_ms": total_duration_ms,
    }
