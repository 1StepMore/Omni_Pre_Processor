"""MCP shared-secret auth (round 16 Phase A4) -- OPP variant.

Identical contract to ol_mcp.auth: when MCP_SHARED_SECRET env
var is set, every tool call must include a matching auth_token
parameter. If the env var is not set, auth is disabled (dev mode).
"""

from __future__ import annotations

import os


def check_auth(provided_secret: str | None) -> tuple[bool, str | None]:
    """Check the shared secret against the configured value."""
    expected = os.environ.get("MCP_SHARED_SECRET")
    if not expected:
        return (True, None)
    if provided_secret == expected:
        return (True, None)
    return (False, "AUTH_FAILED")


def auth_failure_response() -> dict:
    """Standard error response for AUTH_FAILED."""
    return {
        "success": False,
        "error_code": "AUTH_FAILED",
        "message": "Authentication failed: auth_token is missing or incorrect.",
    }
