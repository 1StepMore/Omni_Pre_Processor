"""OPP MCP Server with FastMCP."""

import time
from pathlib import Path
from typing import List, Optional

from fastmcp import FastMCP

from opp.detector import detect_format
from opp.mcp.config import MCPConfig, load_config
from opp.mcp.security import PathValidator
from opp.mcp.serializers import ExtractionResultSerializer
from opp.pipeline import OPPPipeline


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
            resource_path.resolve().relative_to(_config.allowed_directories[0])
        except ValueError:
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

    if "json" in output_formats or (result.extraction_result and result.extraction_result.images):
        if result.extraction_result:
            images_json_path = Path(file_path).with_suffix(".images.json")
            if _config.output_dir:
                images_json_path = Path(_config.output_dir) / images_json_path.name
            try:
                _pipeline.generate_images_json(result.extraction_result, images_json_path)
                if images_json_path.exists():
                    response["images_json_path"] = str(images_json_path)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"Images JSON generation failed: {str(e)}"]

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
                    if not _config.output_dir:
                        xliff_output_path.unlink()
            except ValueError as e:
                response["success"] = False
                response["error"] = str(e)
                response["xliff_error"] = str(e)
            except Exception as e:
                response["warnings"] = response.get("warnings", []) + [f"XLIFF generation failed: {str(e)}"]

    return response


async def batch_extract(
    file_paths: List[str],
    output_formats: Optional[List[str]] = None,
    source_lang: str = "en",
    target_lang: str = "zh",
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
                            if not _config.output_dir: xliff_output_path.unlink()
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

    return {
        "success": True,
        "results": results,
        "successful": successful,
        "failed": failed,
        "total_duration_ms": total_duration_ms,
    }


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


async def generate_xliff(
    file_path: str,
    source_lang: str = "en",
    target_lang: str = "zh",
    output_path: Optional[str] = None,
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


async def generate_markdown(
    file_path: str,
    output_path: Optional[str] = None,
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


def main() -> None:
    config = load_config()
    _init_server(config)

    _mcp.add_tool(ping)
    _mcp.add_tool(extract_document)
    _mcp.add_tool(batch_extract)
    _mcp.add_tool(detect_format_tool)
    _mcp.add_tool(generate_xliff)
    _mcp.add_tool(generate_markdown)

    _mcp.run()