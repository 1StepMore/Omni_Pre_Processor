"""MCP server start command for OPP CLI.

This module provides a programmatic entry point to start the OPP MCP
server, which can be called from the CLI or from Python code.

The standalone entry point ``opp-mcp-server`` (defined in pyproject.toml)
calls ``opp.mcp.server:main`` directly. This module exists as part of the
Task 3.7 CLI split so that ``opp mcp`` subcommand support can be added
without duplicating the server start logic.
"""

from __future__ import annotations

import sys


def start_mcp(argv: list[str] | None = None) -> None:
    """Start the OPP MCP server (stdio transport).

    Parameters
    ----------
    argv:
        Optional argument list (currently unused by the server, but
        accepted for consistency with ``cli.main``).
    """
    from opp.mcp.server import main as mcp_main
    mcp_main()
