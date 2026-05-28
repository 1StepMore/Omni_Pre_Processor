"""Pytest fixtures for OPP MCP tests."""

from pathlib import Path

import pytest


def get_data(result):
    """Extract data dict from tool result (works with both dict and ToolResult)."""
    if hasattr(result, 'structured_content') and result.structured_content is not None:
        return result.structured_content
    return result
