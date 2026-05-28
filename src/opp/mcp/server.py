"""OPP MCP Server with FastMCP."""

import argparse
import time
from pathlib import Path
from typing import List, Optional

from fastmcp import FastMCP
from fastmcp.tools.base import ToolResult
from mcp.types import TextContent

from opp.detector import detect_format
from opp.mcp.config import MCPConfig, load_config
from opp.mcp.security import PathValidator
from opp.mcp.serializers import ExtractionResultSerializer
from opp.pipeline import OPPPipeline


def _is_within_dir(path: Path, directory: Path) -> bool:
    """Check if path is within directory (handles both Unix and Windows paths)."""
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _tool_result(data: dict, summary: str) -> ToolResult:
    """Build a ToolResult with structured_content and human-readable text summary.

    This ensures structuredContent contains the raw dict without JSON-stringification,
    while content provides a brief human-readable summary.
    """
    return ToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=data,
    )


_mcp: Optional[FastMCP] = None
_config: Optional[MCPConfig] = None
_validator: Optional[PathValidator] = None
_pipeline: Optional[OPPPipeline] = None
_serializer: Optional[ExtractionResultSerializer] = None


def _init_server(config: MCPConfig) -> None:
    global _mcp, _config, _validator, _pipeline, _serializer

    _config = config
    _validator = PathValidator(
        allowed_directories=config.allowed_directories,
        max_file_size_bytes=config.max_file_size_bytes,
    )
    _pipeline = OPPPipeline(resource_storage_dir=config.resource_storage_dir)
    _serializer = ExtractionResultSerializer()
    _mcp = FastMCP("OPP MCP Server")


async def extract_document(
    file_path: str,
    output_formats: Optional[List[str]] = None,
    source_lang: str = "en",
    target_lang: str = "zh",
    resource_dir: Optional[str] = None,
) -> ToolResult:
    if output_formats is None:
        output_formats = ["md"]

    if isinstance(output_formats, str):
        output_formats = [output_formats]

    valid_formats = {"md", "xlf", "both"}
    for fmt in output_formats:
        if fmt not in valid_formats:
            return _tool_result(
                {"success": False, "error": f"Invalid output format: '{fmt}'. Valid values are: {sorted(valid_formats)}"},
                f"Error: Invalid output format '{fmt}'",
            )

    if _validator is None:
        return _tool_result(
            {"success": False, "error": "Server not initialized"},
            "Error: Server not initialized",
        )

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return _tool_result(
            {"success": False, "error": validation_result.error or "Path validation failed"},
            f"Error: Path validation failed",
        )

    if resource_dir is not None:
        resource_path = Path(resource_dir)
        if '..' in resource_path.parts:
            return _tool_result(
                {"success": False, "error": "Resource directory path traversal not allowed"},
                "Error: Path traversal not allowed",
            )
        resolved_resource = resource_path.resolve()
        if not any(
            _is_within_dir(resolved_resource, allowed_dir)
            for allowed_dir in _config.allowed_directories
        ):
            return _tool_result(
                {"success": False, "error": "Resource directory must be within allowed directories"},
                "Error: Resource directory not in allowed directories",
            )

    try:
        result = _pipeline.process_file(Path(file_path))
    except Exception as e:
        return _tool_result(
            {"success": False, "error": f"Extraction failed: {str(e)}"},
            f"Error: Extraction failed",
        )

    response = _serializer.serialize(
        result,
        include_base64=True,
        resource_dir=Path(resource_dir) if resource_dir else None,
    )

    if "md" in output_formats or "both" in output_formats:
        if result.extraction_result:
            md_output_path = Path(file_path).with_suffix(".md")
            try:
                _pipeline.generate_markdown(result.extraction_result, md_output_path)
                if md_output_path.exists():
                    with open(md_output_path, "r", encoding="utf-8") as f:
                        response["md_content"] = f.read()
                    md_output_path.unlink()
                images_dir = md_output_path.parent / f"{md_output_path.stem}_images"
                if images_dir.exists():
                    response["images_dir"] = str(images_dir)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]

    if "xlf" in output_formats or "both" in output_formats:
        if result.extraction_result:
            xliff_output_path = Path(file_path).with_suffix(".xlf")
            try:
                _pipeline.generate_xliff(result.extraction_result, xliff_output_path, source_lang, target_lang)
                if xliff_output_path.exists():
                    with open(xliff_output_path, "r", encoding="utf-8") as f:
                        xliff_content = f.read()
                    response["xliff_content"] = xliff_content
                    response["xliff_units_count"] = xliff_content.count("<trans-unit") if xliff_content else 0
                    xliff_output_path.unlink()
            except ValueError as e:
                response["success"] = False
                response["error"] = str(e)
                response["xliff_error"] = str(e)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"XLIFF generation failed: {str(e)}"]

    summary = f"Extracted {response.get('format_type', 'document')}: {len(response.get('extraction_result', {}).get('paragraphs', []))} paragraphs, {response.get('images_stored', 0)} images"
    return _tool_result(response, summary)


async def batch_extract(
    file_paths: List[str],
    output_formats: Optional[List[str]] = None,
    source_lang: str = "en",
    target_lang: str = "zh",
) -> ToolResult:
    if output_formats is None:
        output_formats = ["md"]

    if isinstance(output_formats, str):
        output_formats = [output_formats]

    valid_formats = {"md", "xlf", "both"}
    for fmt in output_formats:
        if fmt not in valid_formats:
            return _tool_result(
                {"success": False, "error": f"Invalid output format: '{fmt}'. Valid values are: {sorted(valid_formats)}"},
                f"Error: Invalid output format '{fmt}'",
            )

    if _validator is None:
        return _tool_result(
            {"success": False, "error": "Server not initialized"},
            "Error: Server not initialized",
        )

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
        return _tool_result(
            {
                "success": False,
                "error": "Path validation failed for one or more files",
                "validation_errors": validation_errors,
                "results": [],
                "successful": 0,
                "failed": len(validation_errors),
                "total_duration_ms": 0.0,
            },
            "Error: Path validation failed",
        )

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
                    md_output_path = Path(file_path).with_suffix(".md")
                    try:
                        _pipeline.generate_markdown(result.extraction_result, md_output_path)
                        if md_output_path.exists():
                            with open(md_output_path, "r", encoding="utf-8") as f:
                                serialized["md_content"] = f.read()
                            md_output_path.unlink()
                        images_dir = md_output_path.parent / f"{md_output_path.stem}_images"
                        if images_dir.exists():
                            serialized["images_dir"] = str(images_dir)
                    except Exception as e:
                        serialized["warnings"] = serialized.get("warnings", []) + [f"Markdown generation failed: {str(e)}"]

            if "xlf" in output_formats or "both" in output_formats:
                if result.extraction_result:
                    xliff_output_path = Path(file_path).with_suffix(".xlf")
                    try:
                        _pipeline.generate_xliff(result.extraction_result, xliff_output_path, source_lang, target_lang)
                        if xliff_output_path.exists():
                            with open(xliff_output_path, "r", encoding="utf-8") as f:
                                xliff_content = f.read()
                            serialized["xliff_content"] = xliff_content
                            serialized["xliff_units_count"] = xliff_content.count("<trans-unit") if xliff_content else 0
                            xliff_output_path.unlink()
                    except ValueError as e:
                        serialized["success"] = False
                        serialized["error"] = str(e)
                        serialized["xliff_error"] = str(e)
                    except Exception as e:
                        serialized["warnings"] = serialized.get("warnings", []) + [f"XLIFF generation failed: {str(e)}"]

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

    return _tool_result(
        {
            "success": True,
            "results": results,
            "successful": successful,
            "failed": failed,
            "total_duration_ms": total_duration_ms,
        },
        f"Batch complete: {successful} successful, {failed} failed",
    )


async def detect_format_tool(file_path: str) -> ToolResult:
    if _validator is None:
        return _tool_result(
            {"success": False, "error": "Server not initialized"},
            "Error: Server not initialized",
        )

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return _tool_result(
            {"success": False, "error": validation_result.error or "Path validation failed"},
            "Error: Path validation failed",
        )

    try:
        fmt, confidence = detect_format(Path(file_path))
        return _tool_result(
            {"success": True, "format": fmt.value, "confidence": confidence},
            f"Detected format: {fmt.value} (confidence: {confidence})",
        )
    except Exception as e:
        return _tool_result(
            {"success": False, "error": f"Format detection failed: {str(e)}"},
            "Error: Format detection failed",
        )


async def generate_xliff(
    file_path: str,
    source_lang: str = "en",
    target_lang: str = "zh",
    output_path: Optional[str] = None,
) -> ToolResult:
    if _validator is None:
        return _tool_result(
            {"success": False, "error": "Server not initialized"},
            "Error: Server not initialized",
        )

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return _tool_result(
            {"success": False, "error": validation_result.error or "Path validation failed"},
            "Error: Path validation failed",
        )

    if output_path is None:
        input_p = Path(file_path)
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".xlf"))

    output_validation = _validator.validate_path(output_path, allow_missing=True)
    if not output_validation.success:
        return _tool_result(
            {"success": False, "error": f"Output path validation failed: {output_validation.error}"},
            "Error: Output path validation failed",
        )

    try:
        result = _pipeline.process_file(Path(file_path))

        if result.extraction_result is None:
            return _tool_result(
                {"success": False, "error": "No extraction result available"},
                "Error: No extraction result available",
            )

        xliff_output_path = _pipeline.generate_xliff(
            result.extraction_result,
            Path(output_path),
            source_lang,
            target_lang,
        )

        with open(xliff_output_path, "r", encoding="utf-8") as f:
            xliff_content = f.read()

        units_count = xliff_content.count("<trans-unit") if xliff_content else 0

        return _tool_result(
            {
                "success": True,
                "xliff_content": xliff_content,
                "output_path": str(xliff_output_path),
                "units_count": units_count,
                "error": None,
            },
            f"Generated XLIFF: {units_count} trans-units",
        )

    except ValueError as e:
        return _tool_result(
            {
                "success": False,
                "error": str(e),
                "xliff_content": None,
                "output_path": None,
                "units_count": 0,
            },
            f"Error: {str(e)}",
        )
    except Exception as e:
        return _tool_result(
            {
                "success": False,
                "error": f"XLIFF generation failed: {str(e)}",
                "xliff_content": None,
                "output_path": None,
                "units_count": 0,
            },
            "Error: XLIFF generation failed",
        )


async def ping() -> ToolResult:
    """Health check endpoint."""
    return _tool_result({"success": True}, "OPP MCP Server is healthy")


async def generate_markdown(
    file_path: str,
    output_path: Optional[str] = None,
) -> ToolResult:
    if _validator is None:
        return _tool_result(
            {"success": False, "error": "Server not initialized"},
            "Error: Server not initialized",
        )

    validation_result = _validator.validate_path(file_path)
    if not validation_result.success:
        return _tool_result(
            {"success": False, "error": validation_result.error or "Path validation failed"},
            "Error: Path validation failed",
        )

    input_p = Path(file_path)

    if output_path is None:
        output_path = str(input_p.with_stem(f"{input_p.stem}_generated").with_suffix(".md"))
    else:
        output_validation = _validator.validate_path(output_path, allow_missing=True)
        if not output_validation.success:
            return _tool_result(
                {"success": False, "error": f"Output path validation failed: {output_validation.error}"},
                "Error: Output path validation failed",
            )

    try:
        result = _pipeline.process_file(input_p)

        if result.extraction_result is None:
            return _tool_result(
                {"success": False, "error": "No extraction result available"},
                "Error: No extraction result available",
            )

        md_output_path = _pipeline.generate_markdown(result.extraction_result, Path(output_path))

        with open(md_output_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        images_count = markdown_content.count("![]")
        images_dir = str(Path(output_path).with_suffix("") / f"{Path(output_path).stem}_images")

        return _tool_result(
            {
                "success": True,
                "markdown_content": markdown_content,
                "output_path": str(md_output_path),
                "images_dir": images_dir,
                "images_count": images_count,
            },
            f"Generated markdown: {len(markdown_content)} chars, {images_count} images",
        )

    except Exception as e:
        return _tool_result(
            {
                "success": False,
                "error": f"Markdown generation failed: {str(e)}",
                "markdown_content": None,
                "output_path": None,
                "images_dir": None,
                "images_count": 0,
            },
            "Error: Markdown generation failed",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="OPP MCP Server")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to YAML configuration file",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    _init_server(config)

    _mcp.add_tool(ping)
    _mcp.add_tool(extract_document)
    _mcp.add_tool(batch_extract)
    _mcp.add_tool(detect_format_tool)
    _mcp.add_tool(generate_xliff)
    _mcp.add_tool(generate_markdown)

    _mcp.run()