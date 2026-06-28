"""Ping tool — health check endpoint."""

from __future__ import annotations

from opp.mcp._errors import mcp_error_boundary, McpError
from opp.mcp.auth import check_auth
from opp.mcp.rate_limiter import check_rate_limit


@mcp_error_boundary
async def ping(auth_token: str | None = None) -> dict:
    """Health check endpoint.

    Returns the OPP version and status. Requires rate-limit + auth checks
    like all other tools (ensures consistent security posture).
    """
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        raise McpError(code="OPP_RATE_LIMITED", message=rate_err)
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        raise McpError(
            code="AUTH_FAILED",
            message="Authentication failed: auth_token is missing or incorrect.",
        )
    from opp import __version__

    return {"success": True, "content": {"version": __version__, "status": "ok"}}
