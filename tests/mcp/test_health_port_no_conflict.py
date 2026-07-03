"""Test P0-T5: OPP health default port must differ from OPP MCP port to avoid bind conflict."""
from opp.mcp import health as health_mod


def test_default_health_port_differs_from_opp_mcp_port():
    """The default health port must NOT be 8766 (which is OPP's MCP port)."""
    # OPP MCP default port is 8766 per AGENTS.md and config.py
    OPP_MCP_DEFAULT_PORT = 8766
    assert health_mod.DEFAULT_HEALTH_PORT != OPP_MCP_DEFAULT_PORT, (
        f"DEFAULT_HEALTH_PORT ({health_mod.DEFAULT_HEALTH_PORT}) collides with "
        f"OPP MCP default port ({OPP_MCP_DEFAULT_PORT}). "
        f"Choose a different port (e.g., 8767)."
    )
