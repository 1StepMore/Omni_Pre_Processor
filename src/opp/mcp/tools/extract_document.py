"""Extract document tool — main extraction entry point.

This is the primary OPP MCP tool. It extracts content from a single
document file (DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML,
MSG, or image) and returns markdown and/or XLIFF depending on the
requested output formats.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from opp.mcp._errors import mcp_error_boundary, McpError

logger = logging.getLogger(__name__)
from opp.mcp.auth import check_auth
from opp.mcp import common as _c
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def extract_document(
    file_path: str,
    output_formats: list[str] | str | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
    resource_dir: str | None = None,
    verbose: bool = False,
    ocr_lang: str | None = None,
    traceparent: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Extract content from a single document file.

    Supports DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG,
    and images. Returns markdown and/or XLIFF depending on
    ``output_formats``.

    Args:
        file_path: Absolute path to the source document.
        output_formats: ``"md"``, ``"xlf"``, ``"both"``, or a list.
        source_lang: Source language code (default ``"zh"``).
        target_lang: Target language code (default ``"en"``).
        resource_dir: Optional directory for extracted resources.
        verbose: Include extra metadata in the response.
        ocr_lang: OCR language code (e.g. ``"chi_sim"``).
        traceparent: Optional W3C Trace Context ``traceparent`` header. The
            dispatcher consumes it to parent this call's span; the tool
            accepts it so the advertised schema round-trips (it is not
            otherwise used inside extraction).
        auth_token: Shared-secret auth token.

    Returns:
        A dict with extraction results (success, md_content, xliff_content,
        images, etc.).
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

    validation_result = _c._validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    # -- resource_dir validation ------------------------------------------
    if resource_dir is not None:
        resource_path = Path(resource_dir)
        if ".." in resource_path.parts:
            raise McpError(
                code="OPP_PATH_DENIED",
                message="Resource directory path traversal not allowed",
            )
        try:
            resolved_resource = resource_path.resolve()
        except (ValueError, OSError) as e:
            raise McpError(
                code="OPP_INVALID_INPUT",
                message=f"Resource directory cannot be resolved: {e}",
            )
        is_resource_allowed = False
        for allowed_dir in _c._config.allowed_directories:
            try:
                resolved_resource.relative_to(Path(allowed_dir).resolve())
                is_resource_allowed = True
                break
            except ValueError:
                continue
        if not is_resource_allowed:
            raise McpError(
                code="OPP_PATH_DENIED",
                message="Resource directory must be within allowed directories",
            )

    # -- run extraction ---------------------------------------------------
    try:
        result = _c._pipeline.process_file(Path(file_path))
    except Exception as e:
        logger.debug("Extraction failed: %s", e)
        raise McpError(
            code="OPP_INTERNAL_ERROR",
            message=f"Extraction failed: {str(e)}",
        )

    response = _c._serializer.serialize(
        result,
        include_base64=True,
        resource_dir=Path(resource_dir) if resource_dir else None,
    )

    response["suggested_pipeline"] = _c._suggest_pipeline(
        result.format_type.value
        if hasattr(result.format_type, "value")
        else str(result.format_type)
    )

    # -- MD output ---------------------------------------------------------
    if "md" in output_formats or "both" in output_formats:
        if result.extraction_result:
            md_output_path = _c._safe_temp_output(".md", Path(file_path).parent)
            try:
                _c._pipeline.generate_markdown(result.extraction_result, md_output_path)
                if md_output_path.exists():
                    with open(md_output_path, "r", encoding="utf-8") as f:
                        response["md_content"] = f.read()
                    _c._safe_unlink(md_output_path)
                images_dir = (
                    md_output_path.parent / f"{Path(file_path).stem}_images"
                )
                if images_dir.exists():
                    _c._tempfiles.add(images_dir)
                    response["images_dir"] = str(images_dir)
            except Exception as e:
                logger.debug("Markdown generation failed: %s", e)
                response.setdefault("warnings", []).append(
                    f"Markdown generation failed: {str(e)}"
                )
            finally:
                _c._safe_unlink(md_output_path)

    # -- images.json output ------------------------------------------------
    if "json" in output_formats or (
        result.extraction_result and result.extraction_result.images
    ):
        if result.extraction_result:
            if _c._config.output_dir:
                images_json_path = _c._safe_temp_output(
                    ".images.json", Path(_c._config.output_dir)
                )
            else:
                images_json_path = _c._safe_temp_output(
                    ".images.json", Path(file_path).parent
                )
            try:
                _c._pipeline.generate_images_json(
                    result.extraction_result, images_json_path
                )
                if images_json_path.exists():
                    response["images_json_path"] = str(images_json_path)
            except Exception as e:
                logger.debug("Images JSON generation failed: %s", e)
                response.setdefault("warnings", []).append(
                    f"Images JSON generation failed: {str(e)}"
                )
            finally:
                if not _c._config.output_dir:
                    _c._safe_unlink(images_json_path)

    # -- XLIFF output ------------------------------------------------------
    if "xlf" in output_formats or "both" in output_formats:
        if result.extraction_result:
            xliff_output_path = _c._safe_temp_output(".xlf", Path(file_path).parent)
            try:
                _c._pipeline.generate_xliff(
                    result.extraction_result,
                    xliff_output_path,
                    source_lang,
                    target_lang,
                    request_id=request_id,
                )
                if xliff_output_path.exists():
                    with open(xliff_output_path, "r", encoding="utf-8") as f:
                        xliff_content = f.read()
                    response["xliff_content"] = xliff_content
                    response["xliff_units_count"] = (
                        xliff_content.count("<trans-unit") if xliff_content else 0
                    )
            except ValueError as e:
                # T-07: never reflect raw exception text to the client.
                # Log the detail server-side; raise the typed error so the
                # boundary returns the standard {success: false, error} envelope.
                logger.warning(
                    "XLIFF generation rejected for %s: %s", file_path, e
                )
                message = "XLIFF output is not supported for this input format."
                raise McpError(
                    code="OPP_XLIFF_UNSUPPORTED",
                    message=message,
                    xliff_error=message,
                ) from e
            except Exception as e:
                logger.debug("XLIFF generation failed: %s", e)
                response.setdefault("warnings", []).append(
                    f"XLIFF generation failed: {str(e)}"
                )
            finally:
                if not _c._config.output_dir:
                    _c._safe_unlink(xliff_output_path)

    # -- Skeleton output (Issue #49) -------------------------------------
    # Always save the skeleton.zip when extraction produced one, so the
    # XLIFF path via MCP is a single tool call (CLI parity: commands/extract.py:273-278).
    # The skeleton is persistent output (required by ORF apply-xliff) so it is NOT
    # added to the _tempfiles cleanup set.
    if result.extraction_result and result.extraction_result.skeleton:
        try:
            sk_output_dir = (
                Path(_c._config.output_dir) if _c._config.output_dir
                else Path(file_path).parent
            )
            sk_result = _c._pipeline.save_skeleton(
                result.extraction_result,
                Path(file_path).stem,
                sk_output_dir,
            )
            if sk_result:
                response["skeleton_path"] = str(sk_result)
        except Exception as e:
            logger.debug("Skeleton save note: %s", e)

    # -- verbose metadata --------------------------------------------------
    if verbose:
        response["detected_format"] = (
            result.format_type.value
            if hasattr(result.format_type, "value")
            else str(result.format_type)
        )
        response["confidence"] = (
            1.0 if response["detected_format"] != "unknown" else 0.0
        )
        steps: list[str] = ["detection", "extraction"]
        if "md" in output_formats or "both" in output_formats:
            steps.append("md_generation")
        if "xlf" in output_formats or "both" in output_formats:
            steps.append("xliff_generation")
        response["processing_steps"] = steps

    if response.get("success") is False:
        return response

    response.pop("success", None)
    return {"success": True, "content": response}
