"""OPP MCP Server using the standard mcp library.

Replaces the previous fastmcp-based implementation. Uses
``mcp.server.Server`` + ``mcp.server.stdio.stdio_server`` for the
transport layer. The seven tool functions are kept as module-level
async functions so existing direct-call tests (e.g.
``opp.mcp.server.extract_document(...)``) and any code that imports
them by name keep working unchanged.

Security layers preserved:
- ``@mcp_error_boundary`` decorator on all 7 tools (including ``ping``)
- ``check_rate_limit()`` (token bucket)
- ``check_auth(auth_token)`` (shared-secret)
- ``PathValidator`` (allowlist, size, traversal, symlinks)
- ``_safe_unlink()``, ``_safe_temp_output()`` (C3 fix)
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import signal as _signal
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from opp.detector import detect_format
from opp.mcp.config import MCPConfig, load_config
from opp.mcp.security import PathValidator
from opp.mcp.serializers import ExtractionResultSerializer
# 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
from opp.mcp.auth import check_auth, auth_failure_response
# H5: token bucket DoS rate limiter (2026-06-20)
from opp.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response
# C12 fix: shared error boundary. The decorator provides a final safety net
# for any UNCAUGHT exception; the existing inner try/except blocks still
# handle expected error conditions, but their `str(e)` values no longer
# reach the client in failure paths handled by the decorator.
from opp.mcp._errors import mcp_error_boundary, validate_file_paths, McpError
from opp.mcp.metrics import (
    STATUS_AUTH_FAILED as _STATUS_AUTH_FAILED,
    STATUS_ERROR as _STATUS_ERROR,
    STATUS_RATE_LIMITED as _STATUS_RATE_LIMITED,
    STATUS_SUCCESS as _STATUS_SUCCESS,
    record_request_from_arguments,
    time_block as _metrics_timer,
)
from opp.mcp.tracing import (
    set_span_status as _tracing_set_status,
    start_call_tool_span as _tracing_start_span,
    inject_traceparent as _tracing_inject_traceparent,
)
from opp.mcp.health import start_health_server as _health_start
from opp.pipeline import OPPPipeline


def _suggest_pipeline(format_type: str) -> str:
    """Map format_type to recommended pipeline.

    Returns one of: 'md_only', 'xliff_only', 'both', 'neither'
    """
    fmt = format_type.lower() if format_type else ""
    if fmt == "pdf":
        return "md_only"
    if fmt in ("docx", "pptx", "epub"):
        return "both"
    if fmt == "unknown":
        return "neither"
    return "md_only"


_config: MCPConfig | None = None
_validator: PathValidator | None = None
_pipeline: OPPPipeline | None = None
_serializer: ExtractionResultSerializer | None = None
_tempfiles: set[Path] = set()


def _init_server(config: MCPConfig) -> None:
    global _config, _validator, _pipeline, _serializer

    _config = config
    _validator = PathValidator(
        allowed_directories=config.allowed_directories,
        max_file_size_bytes=config.max_file_size_bytes,
    )
    _pipeline = OPPPipeline(resource_storage_dir=config.resource_storage_dir)
    _serializer = ExtractionResultSerializer()


def _safe_unlink(path: Path) -> bool:
    """C3 fix: resolve+revalidate path before unlink, then refuse to follow
    symlinks. Returns True if a file was deleted, False otherwise.
    """
    if _validator is None:
        return False
    try:
        resolved = path.resolve()
    except (ValueError, OSError):
        return False
    if path.is_symlink():
        return False
    result = _validator.validate_path(str(resolved), allow_missing=True)
    if not result.success:
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False


def _safe_rmtree(path: Path) -> None:
    """Recursively remove a directory tree. Ignores errors."""
    shutil.rmtree(path, ignore_errors=True)


def _safe_temp_output(suffix: str, parent: Path) -> Path:
    """Create a tempfile inside the resolved parent dir (which must be in an
    allowed dir). Returns the Path. C3 fix: intermediate outputs go in
    tempfiles, never at the input file's with_suffix location.
    OPP#10: registers the created file in _tempfiles for shutdown cleanup.
    """
    parent_resolved = parent.resolve()
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="opp_mcp_", dir=str(parent_resolved))
    os.close(fd)
    p = Path(name)
    _tempfiles.add(p)
    return p


@mcp_error_boundary
async def extract_document(
    file_path: str,
    output_formats: list[str] | str | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
    resource_dir: str | None = None,
    verbose: bool = False,
    ocr_lang: str | None = None,
    auth_token: str | None = None,
) -> dict:
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
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

    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    if resource_dir is not None:
        resource_path = Path(resource_dir)
        if '..' in resource_path.parts:
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
        for allowed_dir in _config.allowed_directories:
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

    try:
        result = _pipeline.process_file(Path(file_path))
    except Exception as e:
        raise McpError(code="OPP_INTERNAL_ERROR", message=f"Extraction failed: {str(e)}")

    response = _serializer.serialize(
        result,
        include_base64=True,
        resource_dir=Path(resource_dir) if resource_dir else None,
    )

    response["suggested_pipeline"] = _suggest_pipeline(
        result.format_type.value if hasattr(result.format_type, "value") else str(result.format_type)
    )

    if "md" in output_formats or "both" in output_formats:
        if result.extraction_result:
            md_output_path = _safe_temp_output(".md", Path(file_path).parent)
            try:
                _pipeline.generate_markdown(result.extraction_result, md_output_path)
                if md_output_path.exists():
                    with open(md_output_path, "r", encoding="utf-8") as f:
                        response["md_content"] = f.read()
                    _safe_unlink(md_output_path)
                images_dir = md_output_path.parent / f"{Path(file_path).stem}_images"
                if images_dir.exists():
                    _tempfiles.add(images_dir)
                    response["images_dir"] = str(images_dir)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]
            finally:
                _safe_unlink(md_output_path)

    if "json" in output_formats or (result.extraction_result and result.extraction_result.images):
        if result.extraction_result:
            if _config.output_dir:
                images_json_path = _safe_temp_output(".images.json", Path(_config.output_dir))
            else:
                images_json_path = _safe_temp_output(".images.json", Path(file_path).parent)
            try:
                _pipeline.generate_images_json(result.extraction_result, images_json_path)
                if images_json_path.exists():
                    response["images_json_path"] = str(images_json_path)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"Images JSON generation failed: {str(e)}"]
            finally:
                if not _config.output_dir:
                    _safe_unlink(images_json_path)

    if "xlf" in output_formats or "both" in output_formats:
        if result.extraction_result:
            xliff_output_path = _safe_temp_output(".xlf", Path(file_path).parent)
            try:
                _pipeline.generate_xliff(
                    result.extraction_result, xliff_output_path,
                    source_lang, target_lang,
                    request_id=request_id,
                )
                if xliff_output_path.exists():
                    with open(xliff_output_path, "r", encoding="utf-8") as f:
                        xliff_content = f.read()
                    response["xliff_content"] = xliff_content
                    response["xliff_units_count"] = xliff_content.count("<trans-unit") if xliff_content else 0
            except ValueError as e:
                response["success"] = False
                response["error"] = str(e)
                response["xliff_error"] = str(e)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"XLIFF generation failed: {str(e)}"]
            finally:
                if not _config.output_dir:
                    _safe_unlink(xliff_output_path)

    if verbose:
        response["detected_format"] = (
            result.format_type.value
            if hasattr(result.format_type, "value")
            else str(result.format_type)
        )
        response["confidence"] = 1.0 if response["detected_format"] != "unknown" else 0.0
        steps: list[str] = ["detection", "extraction"]
        if "md" in output_formats or "both" in output_formats:
            steps.append("md_generation")
        if "xlf" in output_formats or "both" in output_formats:
            steps.append("xliff_generation")
        response["processing_steps"] = steps

    return response


@mcp_error_boundary
async def batch_extract(
    file_paths: list[str],
    output_formats: list[str] | str | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
    auth_token: str | None = None,
) -> dict:
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
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

    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validate_file_paths(file_paths)

    validation_errors = []
    for file_path in file_paths:
        validation_result = _validator.validate_path(file_path)
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
            result = _pipeline.process_file(Path(file_path))
            serialized = _serializer.serialize(result, include_base64=True)

            if "md" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    md_output_path = _safe_temp_output(".md", Path(file_path).parent)
                    try:
                        _pipeline.generate_markdown(result.extraction_result, md_output_path)
                        if md_output_path.exists():
                            with open(md_output_path, "r", encoding="utf-8") as f:
                                serialized["md_content"] = f.read()
                        images_dir = md_output_path.parent / f"{Path(file_path).stem}_images"
                        if images_dir.exists():
                            _tempfiles.add(images_dir)
                            serialized["images_dir"] = str(images_dir)
                    except Exception as e:
                        serialized["warnings"] = serialized.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]
                    finally:
                        _safe_unlink(md_output_path)

            if "xlf" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    xliff_output_path = _safe_temp_output(".xlf", Path(file_path).parent)
                    try:
                        _pipeline.generate_xliff(
                            result.extraction_result, xliff_output_path,
                            source_lang, target_lang,
                            request_id=request_id,
                        )
                        if xliff_output_path.exists():
                            with open(xliff_output_path, "r", encoding="utf-8") as f:
                                xliff_content = f.read()
                            serialized["xliff_content"] = xliff_content
                            serialized["xliff_units_count"] = xliff_content.count("<trans-unit") if xliff_content else 0
                    except ValueError as e:
                        serialized["success"] = False
                        serialized["error"] = str(e)
                        serialized["xliff_error"] = str(e)
                    except Exception as e:
                        serialized["warnings"] = serialized.get("warnings", []) + [f"XLIFF generation failed: {str(e)}"]
                    finally:
                        if not _config.output_dir:
                            _safe_unlink(xliff_output_path)

            results.append({
                "file_path": file_path,
                **serialized,
            })
            successful += 1
        except Exception as e:
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


@mcp_error_boundary
async def detect_format_tool(file_path: str, auth_token: str | None = None) -> dict:
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _validator.validate_path(file_path)
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
        raise McpError(code="OPP_INTERNAL_ERROR", message=f"Format detection failed: {str(e)}")


@mcp_error_boundary
async def generate_xliff(
    file_path: str,
    source_lang: str = "zh",
    target_lang: str = "en",
    output_path: str | None = None,
    auth_token: str | None = None,
) -> dict:
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    request_id = str(uuid.uuid4())
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    if output_path is None:
        input_p = Path(file_path)
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".xlf"))

    output_validation = _validator.validate_path(output_path, allow_missing=True)
    if not output_validation.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=f"Output path validation failed: {output_validation.error}",
        )

    try:
        result = _pipeline.process_file(Path(file_path))

        if result.extraction_result is None:
            raise McpError(code="OPP_INTERNAL_ERROR", message="No extraction result available")

        xliff_output_path = _pipeline.generate_xliff(
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
        raise McpError(code="OPP_INTERNAL_ERROR", message=f"XLIFF generation failed: {str(e)}")


@mcp_error_boundary
async def ping(auth_token: str | None = None) -> dict:
    """Health check endpoint."""
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
    from opp import __version__
    return {"success": True, "content": {"version": __version__, "status": "ok"}}


@mcp_error_boundary
async def generate_markdown(
    file_path: str,
    output_path: str | None = None,
    style_mapping: dict[str, int] | None = None,
    embed_images: bool = True,
    auth_token: str | None = None,
) -> dict:
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    input_p = Path(file_path)

    if output_path is None:
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".md"))
    else:
        output_validation = _validator.validate_path(output_path, allow_missing=True)
        if not output_validation.success:
            raise McpError(
                code="OPP_PATH_DENIED",
                message=f"Output path validation failed: {output_validation.error}",
            )

    try:
        result = _pipeline.process_file(input_p)

        if result.extraction_result is None:
            raise McpError(code="OPP_INTERNAL_ERROR", message="No extraction result available")

        md_output_path = _pipeline.generate_markdown(
            result.extraction_result,
            Path(output_path),
            style_mapping=style_mapping,
            embed_images=embed_images,
        )

        with open(md_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        images_count = markdown_content.count("![]")
        images_dir = str(Path(output_path).with_suffix("") / f"{Path(output_path).stem}_images")

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
        raise McpError(code="OPP_INTERNAL_ERROR", message=f"Markdown generation failed: {str(e)}")


@mcp_error_boundary
async def save_skeleton(
    file_path: str,
    base_name: str = "document",
    output_dir: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Save skeleton ZIP file from extracted document.

    Runs OPP extraction (process_file), then saves the skeleton via
    OPPPipeline.save_skeleton. Returns the skeleton path. The skeleton
    is required by ORF's apply_xliff as the input_file arg, so this tool
    completes the OPP MCP surface for full-pipeline use.
    """
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(code="AUTH_FAILED", message="Authentication failed: auth_token is missing or incorrect.")
    if _validator is None:
        raise McpError(code="OPP_INTERNAL_ERROR", message="Server not initialized")

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        raise McpError(
            code="OPP_PATH_DENIED",
            message=validation_result.error or "Path validation failed",
        )

    output_path = Path(output_dir) if output_dir else Path(file_path).parent
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        result = _pipeline.process_file(Path(file_path))
        if result.extraction_result is None:
            raise McpError(code="OPP_INTERNAL_ERROR", message="No extraction result")

        skeleton_path = _pipeline.save_skeleton(
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
        raise McpError(code="OPP_INTERNAL_ERROR", message=f"Skeleton save failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────
# Standard mcp library transport layer
# ─────────────────────────────────────────────────────────────────────

# Tool schemas exposed to MCP clients (used by @server.list_tools()).
_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "extract_document",
        "description": (
            "Extract content from a single document file. Supports DOCX, PPTX, "
            "PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and images. "
            "Returns markdown and/or XLIFF depending on output_formats."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the source document."},
                "output_formats": {
                    "oneOf": [
                        {"type": "string", "enum": ["md", "xlf", "both"]},
                        {
                            "type": "array",
                            "items": {"type": "string", "enum": ["md", "xlf", "both"]},
                        },
                    ],
                    "description": "Output formats; default is ['md'].",
                },
                "source_lang": {"type": "string", "default": "zh", "description": "Source language code."},
                "target_lang": {"type": "string", "default": "en", "description": "Target language code."},
                "resource_dir": {"type": "string", "description": "Directory to store extracted resources."},
                "verbose": {"type": "boolean", "default": False, "description": "Include extra metadata (detected_format, confidence, processing_steps) in the response."},
                "ocr_lang": {"type": "string", "description": "OCR language code (e.g. 'chi_sim', 'jpn', 'fra'). Sets OPP_OCR_LANG env var before extraction. Default: 'eng'."},
                "traceparent": {
                    "type": "string",
                    "description": "Optional W3C Trace Context traceparent header to make this span a child of an upstream trace.",
                },
                "auth_token": {"type": "string", "description": "Shared secret for MCP auth (when MCP_SHARED_SECRET is set)."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "batch_extract",
        "description": (
            "Process multiple files in one request. Returns per-file extraction "
            "results plus aggregate counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of absolute file paths to extract.",
                },
                "output_formats": {
                    "oneOf": [
                        {"type": "string", "enum": ["md", "xlf", "both"]},
                        {
                            "type": "array",
                            "items": {"type": "string", "enum": ["md", "xlf", "both"]},
                        },
                    ],
                    "description": "Output formats; default is ['md'].",
                },
                "source_lang": {"type": "string", "default": "zh"},
                "target_lang": {"type": "string", "default": "en"},
                "auth_token": {"type": "string"},
            },
            "required": ["file_paths"],
        },
    },
    {
        "name": "detect_format_tool",
        "description": (
            "Identify the file format using magic-bytes detection. Returns "
            "the format name and a confidence score in [0, 1]."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file to inspect."},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "generate_xliff",
        "description": (
            "Convert a document to XLIFF format for translation workflows. "
            "Requires source and target language codes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "source_lang": {"type": "string", "default": "zh"},
                "target_lang": {"type": "string", "default": "en"},
                "output_path": {"type": "string", "description": "Optional output XLIFF path."},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "generate_markdown",
        "description": "Convert a document to Markdown format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "output_path": {"type": "string"},
                "style_mapping": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                    "description": "Optional mapping from style name to heading level.",
                },
                "embed_images": {"type": "boolean", "default": True},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "save_skeleton",
        "description": (
            "Save skeleton ZIP from an extracted DOCX/PPTX. The skeleton is "
            "required by ORF's apply_xliff for XLIFF->DOCX/PPTX backfill."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "base_name": {"type": "string", "default": "document"},
                "output_dir": {"type": "string"},
                "auth_token": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "ping",
        "description": "Health check endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "auth_token": {"type": "string"},
            },
        },
    },
]


# Dispatch table: tool name -> module-level async function
_TOOL_DISPATCH: dict[str, Any] = {
    "extract_document": extract_document,
    "batch_extract": batch_extract,
    "detect_format_tool": detect_format_tool,
    "generate_xliff": generate_xliff,
    "generate_markdown": generate_markdown,
    "save_skeleton": save_skeleton,
    "ping": ping,
}


# Build the standard mcp Server instance. The fastmcp 3.4.2 stdio
# transport has a known bug (server reads stdin but never writes
# responses); the standard library's stdio_server() works correctly.
server: Server = Server("OPP MCP Server")


@server.list_tools()
async def _handle_list_tools() -> list[types.Tool]:
    return [types.Tool(**schema) for schema in _TOOL_SCHEMAS]


@server.call_tool()
async def _handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.ContentBlock]:
    """Dispatch a tool call to the appropriate module-level function.

    The ``mcp_error_boundary`` decorator on the tool functions already
    converts uncaught exceptions into safe error dicts, but the standard
    mcp library doesn't handle exceptions raised by ``call_tool`` the
    same way FastMCP did. The wrapper below provides an additional
    safety net: any exception that escapes the decorator is logged with
    full traceback server-side and returned to the client as an opaque
    error response (no internals leaked).
    """
    import logging
    import traceback

    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        record_request_from_arguments(
            name, arguments, _STATUS_ERROR, 0.0,
        )
        with _tracing_start_span(name, arguments) as _span:
            _tracing_set_status(_span, "error", error_code="OPP_UNKNOWN_TOOL")
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "success": False,
                        "error": {"code": "OPP_UNKNOWN_TOOL", "message": f"Unknown tool: {name!r}"},
                        "error_code": "OPP_UNKNOWN_TOOL",
                        "message": f"Unknown tool: {name!r}",
                    }
                ),
            )
        ]

    logger = logging.getLogger("opp_mcp.server")
    timer = _metrics_timer()
    _traceparent_arg = (arguments or {}).get("traceparent")
    with _tracing_start_span(name, arguments, traceparent=_traceparent_arg) as _span:
        try:
            result = await fn(**(arguments or {}))
        except Exception:
            duration = timer.seconds()
            logger.exception("Unhandled error in tool %s", name)
            record_request_from_arguments(
                name, arguments, _STATUS_ERROR, duration,
            )
            _tracing_set_status(
                _span, "error",
                error_code="OPP_INTERNAL_ERROR",
                duration_ms=duration * 1000.0,
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": {
                                "code": "OPP_INTERNAL_ERROR",
                                "message": "An internal error occurred. Check server logs.",
                            },
                            "error_code": "OPP_INTERNAL_ERROR",
                            "message": "An internal error occurred. Check server logs.",
                            "tool": name,
                            "traceback": traceback.format_exc(limit=10),
                        }
                    ),
                )
            ]

        if not isinstance(result, dict):
            result = {"success": True, "data": result}

        if name == "extract_document" and isinstance(result, dict):
            tp = _tracing_inject_traceparent(_span)
            if tp is not None:
                result["traceparent"] = tp

        status = _classify_status(result)
        record_request_from_arguments(
            name, arguments, status, timer.seconds(),
        )
        _tracing_set_status(
            _span, status,
            error_code=result.get("error_code") if isinstance(result, dict) else None,
            duration_ms=timer.seconds() * 1000.0,
        )

        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _classify_status(result: dict[str, Any]) -> str:
    """Map a tool's result dict to a coarse status label for metrics."""
    if not isinstance(result, dict):
        return _STATUS_ERROR
    if result.get("success") is True:
        return _STATUS_SUCCESS
    code = result.get("error_code")
    if code == "RATE_LIMITED":
        return _STATUS_RATE_LIMITED
    if code == "AUTH_FAILED":
        return _STATUS_AUTH_FAILED
    return _STATUS_ERROR


logger = logging.getLogger("opp_mcp.server")


def _cleanup_tempfiles() -> int:
    """Unlink all tracked temp files and directories. Returns count removed."""
    removed = 0
    for p in list(_tempfiles):
        try:
            if p.exists() and not p.is_symlink():
                if p.is_dir():
                    _safe_rmtree(p)
                else:
                    p.unlink()
                removed += 1
        except OSError as e:
            logger.debug(f"Failed to unlink temp file {p}: {e}")
        finally:
            _tempfiles.discard(p)
    if removed:
        logger.debug(f"OPP#10 cleanup: unlinked {removed} temp file(s)")
    return removed


def _cleanup_resource_dir() -> int:
    """Recursively remove the resource_storage_dir. Returns count of files removed.
    OPP#10: only called when cleanup_on_shutdown=True.
    """
    if _config is None or _config.cleanup_on_shutdown is False:
        return 0
    resource_dir = _config.resource_storage_dir
    if not resource_dir.exists():
        return 0
    resolved = str(resource_dir.resolve())
    if resolved in ("/", str(Path.cwd().resolve())):
        logger.error(
            f"OPP#10 cleanup refused: resource_storage_dir={resource_dir} "
            f"resolves to a system path, refusing to rmtree"
        )
        return 0
    count = sum(1 for _ in resource_dir.rglob("*") if _.is_file())
    try:
        shutil.rmtree(resource_dir)
        logger.info(
            f"OPP#10 cleanup: removed resource dir {resource_dir} "
            f"({count} file(s))"
        )
        return count
    except OSError as e:
        logger.error(f"OPP#10 cleanup failed to rmtree {resource_dir}: {e}")
        return 0


def _shutdown_cleanup() -> None:
    """Run on atexit / signal. Always cleans temp files; cleans resource
    dir only if cleanup_on_shutdown=True.
    """
    n_temp = 0
    n_res = 0
    try:
        n_temp = _cleanup_tempfiles()
    except Exception as e:
        logger.error(f"OPP#10 temp cleanup failed: {e}")
    try:
        n_res = _cleanup_resource_dir()
    except Exception as e:
        logger.error(f"OPP#10 resource cleanup failed: {e}")
    if n_temp or n_res:
        logger.info(
            f"OPP#10 shutdown cleanup: {n_temp} temp file(s), "
            f"{n_res} resource file(s)"
        )


atexit.register(_shutdown_cleanup)


def _signal_handler(signum: int, frame: Any) -> None:
    logger.info(f"OPP#10: received signal {signum}, running cleanup")
    _shutdown_cleanup()
    _signal.default_int_handler(signum, frame)


async def _run() -> None:
    """Async entry point: drive the stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
            raise_exceptions=False,
        )


def main() -> None:
    """Synchronous entry point invoked by ``python -m opp.mcp.server``."""
    config = load_config()
    _init_server(config)
    _health_start()
    if not os.environ.get("OPP_MCP_DISABLE_SIGNAL_HANDLERS"):
        try:
            _signal.signal(_signal.SIGTERM, _signal_handler)
            _signal.signal(_signal.SIGINT, _signal_handler)
            logger.debug("OPP#10: installed SIGTERM/SIGINT handlers")
        except (ValueError, OSError):
            pass
    anyio.run(_run)


if __name__ == "__main__":
    main()
