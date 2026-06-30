"""OPP MCP tool functions.

Each tool function lives in its own module under this package. Re-export
all of them here so ``opp.mcp.server`` and direct importers can access
them via ``opp.mcp.tools``.
"""

from opp.mcp.tools.ping import ping
from opp.mcp.tools.detect_format import detect_format_tool
from opp.mcp.tools.save_skeleton import save_skeleton
from opp.mcp.tools.generate import generate_markdown, generate_xliff
from opp.mcp.tools.extract_document import extract_document
from opp.mcp.tools.batch_extract import batch_extract
from opp.mcp.tools.validate_xliff import validate_xliff

__all__ = [
    "ping",
    "detect_format_tool",
    "save_skeleton",
    "generate_markdown",
    "generate_xliff",
    "extract_document",
    "batch_extract",
    "validate_xliff",
]
