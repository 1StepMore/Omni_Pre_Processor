"""OPP tool implementation for Hermes plugin."""

import subprocess
import json
import os
from typing import Any, Optional


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


def check_opp_requirements() -> tuple[bool, Optional[str]]:
    """Check if OPP MCP server is available and configured."""
    try:
        import opp
        return True, None
    except ImportError:
        return False, "OPP package not installed. Install with: pip install opp[mcp]"


def opp_handler(
    file_path: str,
    output_formats: Optional[list[str]] = None,
    source_lang: str = "en",
    target_lang: str = "zh",
    resource_dir: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """Handle OPP document extraction via Python API.

    This handler calls the OPP MCP server implementation directly via Python,
    avoiding the stdio transport layer for synchronous operation.
    """
    if output_formats is None:
        output_formats = ["md"]

    allowed_dirs = os.environ.get("OPP_MCP_ALLOWED_DIRS", "")
    if not allowed_dirs:
        return {
            "success": False,
            "error": "OPP_MCP_ALLOWED_DIRS environment variable not set. "
                     "Please configure allowed directories for OPP extraction.",
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
    except Exception as e:
        return {
            "success": False,
            "error": f"Extraction failed: {str(e)}",
        }