"""OPP tool implementation for Hermes plugin."""

import os
from typing import Any


OPP_SCHEMA = {
    "name": "opp_extract",
    "description": "Extract content from documents (DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Images with OCR)",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the document file to extract content from",
            },
            "output_formats": {
                "type": "array",
                "items": {"type": "string", "enum": ["md", "xlf", "both"]},
                "default": ["md"],
                "description": "Output formats: md (markdown), xlf (XLIFF for translation), both",
            },
            "source_lang": {
                "type": "string",
                "default": "en",
                "description": "Source language code (e.g., 'en', 'zh')",
            },
            "target_lang": {
                "type": "string",
                "default": "zh",
                "description": "Target language code for XLIFF generation",
            },
            "resource_dir": {
                "type": "string",
                "description": "Directory to store extracted images (optional)",
            },
        },
        "required": ["file_path"],
    },
}


def check_opp_requirements() -> tuple[bool, str | None]:
    """Check if OPP MCP server is available and configured."""
    import importlib.util
    if importlib.util.find_spec("opp"):
        return True, None
    return False, "OPP package not installed. Install with: pip install opp[mcp]"


def opp_handler(
    file_path: str,
    output_formats: list[str] | None = None,
    source_lang: str = "en",
    target_lang: str = "zh",
    resource_dir: str | None = None,
    **kwargs: Any,
) -> dict:
    """Handle OPP document extraction via Python API.

    This handler calls the OPP MCP server implementation directly via Python,
    avoiding the stdio transport layer for synchronous operation.
    """
    if output_formats is None:
        output_formats = ["md"]

    # 2026-11-06 (ADR 0007 Phase 2B-lite): resolve the allowlist with the
    # same precedence as opp.mcp.config._load_from_env
    # (MCP_ALLOWED_DIRECTORIES > OPP_MCP_ALLOWED_DIRS) so the Hermes entry
    # no longer hard-requires the module-specific variable alone.
    allowed_dirs = (
        os.environ.get("MCP_ALLOWED_DIRECTORIES")
        or os.environ.get("OPP_MCP_ALLOWED_DIRS")
        or ""
    )
    if not allowed_dirs:
        return {
            "success": False,
            "error": "No allowlist configured: set MCP_ALLOWED_DIRECTORIES "
                     "(or OPP_MCP_ALLOWED_DIRS) before OPP extraction.",
        }

    try:
        from opp.mcp.server import extract_document as mcp_extract
        from opp.mcp.config import load_config
        from opp.mcp.server import _init_server

        config = load_config()
        _init_server(config)

        result = mcp_extract(
            file_path=file_path,
            output_formats=output_formats,
            source_lang=source_lang,
            target_lang=target_lang,
            resource_dir=resource_dir,
        )
        return result

    except ImportError as e:
        return {
            "success": False,
            "error": f"OPP MCP server not available: {str(e)}. "
                     "Ensure opp[mcp] is installed.",
        }
    except Exception as e:  # expected — error is returned to caller
        return {
            "success": False,
            "error": f"Extraction failed: {str(e)}",
        }