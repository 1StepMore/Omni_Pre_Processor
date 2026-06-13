"""OPP MCP Server with FastMCP."""

import os
import tempfile
import time
from pathlib import Path
from typing import List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from opp.detector import detect_format
from opp.mcp.config import MCPConfig, load_config
from opp.mcp.security import PathValidator
from opp.mcp.serializers import ExtractionResultSerializer
# C12 fix: shared error boundary. The decorator provides a final safety net
# for any UNCAUGHT exception; the existing inner try/except blocks still
# handle expected error conditions, but their `str(e)` values no longer
# reach the client in failure paths handled by the decorator.
from opp.mcp._errors import mcp_error_boundary, validate_file_paths
from opp.pipeline import OPPPipeline


_mcp: FastMCP | None = None
_config: MCPConfig | None = None
_validator: PathValidator | None = None
_pipeline: OPPPipeline | None = None
_serializer: ExtractionResultSerializer | None = None


def _init_server(config: MCPConfig) -> None:
    global _mcp, _config, _validator, _pipeline, _serializer

    _config = config
    _validator = PathValidator(
        allowed_directories=config.allowed_directories,
        max_file_size_bytes=config.max_file_size_bytes,
    )
    _pipeline = OPPPipeline(resource_storage_dir=config.resource_storage_dir)
    _serializer = ExtractionResultSerializer()
    _mcp = FastMCP("OPP MCP Server") if FastMCP is not None else None


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
    # Reject symlinks: unlink() follows them and could delete the target
    if path.is_symlink():
        return False
    # Re-validate against allowlist
    result = _validator.validate_path(str(resolved), allow_missing=True)
    if not result.success:
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False


def _safe_temp_output(suffix: str, parent: Path) -> Path:
    """Create a tempfile inside the resolved parent dir (which must be in an
    allowed dir). Returns the Path. C3 fix: intermediate outputs go in
    tempfiles, never at the input file's with_suffix location.
    """
    parent_resolved = parent.resolve()
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="opp_mcp_", dir=str(parent_resolved))
    os.close(fd)
    return Path(name)


@mcp_error_boundary
async def extract_document(
    file_path: str,
    output_formats: list[str] | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
    resource_dir: str | None = None,
) -> dict:
    if output_formats is None:
        output_formats = ["md"]

    if isinstance(output_formats, str):
        output_formats = [output_formats]

    valid_formats = {"md", "xlf", "both"}
    for fmt in output_formats:
        if fmt not in valid_formats:
            return {
                "success": False,
                "error": f"Invalid output format: '{fmt}'. Valid values are: {sorted(valid_formats)}",
            }

    if _validator is None:
        return {
            "success": False,
            "error": "Server not initialized",
        }

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return {
            "success": False,
            "error": validation_result.error or "Path validation failed",
        }

    if resource_dir is not None:
        resource_path = Path(resource_dir)
        if '..' in resource_path.parts:
            return {
                "success": False,
                "error": "Resource directory path traversal not allowed",
            }
        try:
            resolved_resource = resource_path.resolve()
        except (ValueError, OSError) as e:
            return {
                "success": False,
                "error": f"Resource directory cannot be resolved: {e}",
            }
        # C6 fix: iterate ALL allowed_directories; pre-fix only checked [0].
        is_resource_allowed = False
        for allowed_dir in _config.allowed_directories:
            try:
                resolved_resource.relative_to(Path(allowed_dir).resolve())
                is_resource_allowed = True
                break
            except ValueError:
                continue
        if not is_resource_allowed:
            return {
                "success": False,
                "error": "Resource directory must be within allowed directories",
            }

    try:
        result = _pipeline.process_file(Path(file_path))
    except Exception as e:
        return {
            "success": False,
            "error": f"Extraction failed: {str(e)}",
        }

    response = _serializer.serialize(
        result,
        include_base64=True,
        resource_dir=Path(resource_dir) if resource_dir else None,
    )

    if "md" in output_formats or "both" in output_formats:
        if result.extraction_result:
            # C3 fix: write to a tempfile inside the input dir, then safe_unlink
            md_output_path = _safe_temp_output(".md", Path(file_path).parent)
            try:
                _pipeline.generate_markdown(result.extraction_result, md_output_path)
                if md_output_path.exists():
                    with open(md_output_path, "r", encoding="utf-8") as f:
                        response["md_content"] = f.read()
                    _safe_unlink(md_output_path)
                images_dir = md_output_path.parent / f"{Path(file_path).stem}_images"
                if images_dir.exists():
                    response["images_dir"] = str(images_dir)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]
            finally:
                _safe_unlink(md_output_path)

    if "json" in output_formats or (result.extraction_result and result.extraction_result.images):
        if result.extraction_result:
            # C3 fix: write to a tempfile; safe_unlink in finally
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
            # C3 fix: write to a tempfile; safe_unlink in finally
            xliff_output_path = _safe_temp_output(".xlf", Path(file_path).parent)
            try:
                _pipeline.generate_xliff(result.extraction_result, xliff_output_path, source_lang, target_lang)
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

    return response


@mcp_error_boundary
async def batch_extract(
    file_paths: list[str],
    output_formats: list[str] | None = None,
    source_lang: str = "zh",
    target_lang: str = "en",
) -> dict:
    if output_formats is None:
        output_formats = ["md"]

    if isinstance(output_formats, str):
        output_formats = [output_formats]

    valid_formats = {"md", "xlf", "both"}
    for fmt in output_formats:
        if fmt not in valid_formats:
            return {
                "success": False,
                "error": f"Invalid output format: '{fmt}'. Valid values are: {sorted(valid_formats)}",
            }

    if _validator is None:
        return {
            "success": False,
            "error": "Server not initialized",
        }

    # S-5: enforce file count limit before processing
    validate_file_paths(file_paths)

    # Validate ALL paths BEFORE processing any (fail-fast)
    validation_errors = []
    for file_path in file_paths:
        validation_result = _validator.validate_path(file_path)
        if not validation_result.success:
            validation_errors.append({
                "file_path": file_path,
                "error": validation_result.error or "Path validation failed",
            })

    if validation_errors:
        return {
            "success": False,
            "error": "Path validation failed for one or more files",
            "validation_errors": validation_errors,
            "results": [],
            "successful": 0,
            "failed": len(validation_errors),
            "total_duration_ms": 0.0,
        }

    # Process files sequentially
    results = []
    successful = 0
    failed = 0
    start_time = time.time()

    for file_path in file_paths:
        try:
            result = _pipeline.process_file(Path(file_path))
            serialized = _serializer.serialize(result, include_base64=True)

            # Handle output formats for each file
            if "md" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    # C3 fix: tempfile + safe_unlink
                    md_output_path = _safe_temp_output(".md", Path(file_path).parent)
                    try:
                        _pipeline.generate_markdown(result.extraction_result, md_output_path)
                        if md_output_path.exists():
                            with open(md_output_path, "r", encoding="utf-8") as f:
                                serialized["md_content"] = f.read()
                        images_dir = md_output_path.parent / f"{Path(file_path).stem}_images"
                        if images_dir.exists():
                            serialized["images_dir"] = str(images_dir)
                    except Exception as e:
                        serialized["warnings"] = serialized.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]
                    finally:
                        _safe_unlink(md_output_path)

            if "xlf" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    # C3 fix: tempfile + safe_unlink
                    xliff_output_path = _safe_temp_output(".xlf", Path(file_path).parent)
                    try:
                        _pipeline.generate_xliff(result.extraction_result, xliff_output_path, source_lang, target_lang)
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
async def detect_format_tool(file_path: str) -> dict:
    if _validator is None:
        return {
            "success": False,
            "error": "Server not initialized",
        }

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return {
            "success": False,
            "error": validation_result.error or "Path validation failed",
        }

    try:
        fmt, confidence = detect_format(Path(file_path))
        return {
            "success": True,
            "format": fmt.value,
            "confidence": confidence,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Format detection failed: {str(e)}",
        }


@mcp_error_boundary
async def generate_xliff(
    file_path: str,
    source_lang: str = "zh",
    target_lang: str = "en",
    output_path: str | None = None,
) -> dict:
    if _validator is None:
        return {
            "success": False,
            "error": "Server not initialized",
        }

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return {
            "success": False,
            "error": validation_result.error or "Path validation failed",
        }

    if output_path is None:
        input_p = Path(file_path)
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".xlf"))

    output_validation = _validator.validate_path(output_path, allow_missing=True)
    if not output_validation.success:
        return {
            "success": False,
            "error": f"Output path validation failed: {output_validation.error}",
        }

    try:
        result = _pipeline.process_file(Path(file_path))

        if result.extraction_result is None:
            return {
                "success": False,
                "error": "No extraction result available",
            }

        xliff_output_path = _pipeline.generate_xliff(
            result.extraction_result,
            Path(output_path),
            source_lang,
            target_lang,
        )

        with open(xliff_output_path, "r", encoding="utf-8") as f:
            xliff_content = f.read()

        units_count = xliff_content.count("<trans-unit") if xliff_content else 0

        return {
            "success": True,
            "xliff_content": xliff_content,
            "output_path": str(xliff_output_path),
            "units_count": units_count,
            "error": None,
        }

    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "xliff_content": None,
            "output_path": None,
            "units_count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"XLIFF generation failed: {str(e)}",
            "xliff_content": None,
            "output_path": None,
            "units_count": 0,
        }


async def ping() -> dict:
    """Health check endpoint."""
    return {"success": True}


@mcp_error_boundary
async def generate_markdown(
    file_path: str,
    output_path: str | None = None,
) -> dict:
    if _validator is None:
        return {
            "success": False,
            "error": "Server not initialized",
        }

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return {
            "success": False,
            "error": validation_result.error or "Path validation failed",
        }

    input_p = Path(file_path)

    if output_path is None:
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".md"))
    else:
        output_validation = _validator.validate_path(output_path, allow_missing=True)
        if not output_validation.success:
            return {
                "success": False,
                "error": f"Output path validation failed: {output_validation.error}",
            }

    try:
        result = _pipeline.process_file(input_p)

        if result.extraction_result is None:
            return {
                "success": False,
                "error": "No extraction result available",
            }

        md_output_path = _pipeline.generate_markdown(result.extraction_result, Path(output_path))

        with open(md_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        images_count = markdown_content.count("![]")
        images_dir = str(Path(output_path).with_suffix("") / f"{Path(output_path).stem}_images")

        return {
            "success": True,
            "markdown_content": markdown_content,
            "output_path": str(md_output_path),
            "images_dir": images_dir,
            "images_count": images_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Markdown generation failed: {str(e)}",
            "markdown_content": None,
            "output_path": None,
            "images_dir": None,
            "images_count": 0,
        }


@mcp_error_boundary
async def save_skeleton(
    file_path: str,
    base_name: str = "document",
    output_dir: str | None = None,
) -> dict:
    """Save skeleton ZIP file from extracted document.

    Runs OPP extraction (process_file), then saves the skeleton via
    OPPPipeline.save_skeleton. Returns the skeleton path. The skeleton
    is required by ORF's apply_xliff as the input_file arg, so this tool
    completes the OPP MCP surface for full-pipeline use.

    Args:
        file_path: Path to the source document (DOCX/PPTX/PDF/etc.).
        base_name: Output file base name (default "document").
        output_dir: Output directory (default: same dir as file_path).

    Returns:
        JSON dict with success, skeleton_path (or None if no skeleton), error.
    """
    if _validator is None:
        return {
            "success": False,
            "skeleton_path": None,
            "error": "Server not initialized",
        }

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return {
            "success": False,
            "skeleton_path": None,
            "error": validation_result.error or "Path validation failed",
        }

    output_path = Path(output_dir) if output_dir else Path(file_path).parent
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        result = _pipeline.process_file(Path(file_path))
        if result.extraction_result is None:
            return {
                "success": False,
                "skeleton_path": None,
                "error": "No extraction result",
            }

        skeleton_path = _pipeline.save_skeleton(
            result.extraction_result, base_name, output_path,
        )
        return {
            "success": True,
            "skeleton_path": str(skeleton_path) if skeleton_path else None,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "skeleton_path": None,
            "error": f"Skeleton save failed: {str(e)}",
        }


def main() -> None:
    config = load_config()
    _init_server(config)

    _mcp.add_tool(ping)
    _mcp.add_tool(extract_document)
    _mcp.add_tool(batch_extract)
    _mcp.add_tool(detect_format_tool)
    _mcp.add_tool(generate_xliff)
    _mcp.add_tool(generate_markdown)
    _mcp.add_tool(save_skeleton)

    _mcp.run()