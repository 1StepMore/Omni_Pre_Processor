"""Test P0-T4: cleanup_on_shutdown default must be False to prevent silent data loss.

The AGENTS.md documents the default as `false`. If the default is `True`,
the MCP server recursively removes mcp_resources/ on every restart,
causing silent data loss of extracted resources.
"""

from __future__ import annotations

import os
from pathlib import Path

from opp.mcp.config import MCPConfig


class TestCleanupOnShutdownDefaultIsFalse:
    """P0-T4: Both MCPConfig default and load_config() fallback must be False."""

    def test_mcpconfig_dataclass_default_is_false(self):
        """MCPConfig.cleanup_on_shutdown default must be False."""
        fields = {f.name: f for f in MCPConfig.__dataclass_fields__.values()}
        assert "cleanup_on_shutdown" in fields
        field = fields["cleanup_on_shutdown"]
        assert field.default is False, (
            f"MCPConfig.cleanup_on_shutdown default is {field.default}, expected False. "
            f"Setting True causes silent deletion of mcp_resources/ on every server restart."
        )

    def test_load_config_default_is_false(self, tmp_path: Path):
        """load_config() fallback must be False when env var is unset."""
        from opp.mcp.config import load_config

        original_cleanup = os.environ.pop("OPP_MCP_CLEANUP_ON_SHUTDOWN", None)
        original_dirs = os.environ.get("OPP_MCP_ALLOWED_DIRS")
        try:
            os.environ["OPP_MCP_ALLOWED_DIRS"] = str(tmp_path)
            cfg = load_config()
            assert cfg.cleanup_on_shutdown is False, (
                f"load_config() defaulted cleanup_on_shutdown to "
                f"{cfg.cleanup_on_shutdown}, expected False"
            )
        finally:
            if original_cleanup is not None:
                os.environ["OPP_MCP_CLEANUP_ON_SHUTDOWN"] = original_cleanup
            if original_dirs is not None:
                os.environ["OPP_MCP_ALLOWED_DIRS"] = original_dirs
            else:
                os.environ.pop("OPP_MCP_ALLOWED_DIRS", None)

    def test_env_var_true_overrides_default(self, tmp_path: Path):
        """OPP_MCP_CLEANUP_ON_SHUTDOWN=true must still work (opt-in to cleanup)."""
        from opp.mcp.config import load_config

        original_cleanup = os.environ.get("OPP_MCP_CLEANUP_ON_SHUTDOWN")
        original_dirs = os.environ.get("OPP_MCP_ALLOWED_DIRS")
        try:
            os.environ["OPP_MCP_ALLOWED_DIRS"] = str(tmp_path)
            os.environ["OPP_MCP_CLEANUP_ON_SHUTDOWN"] = "true"
            cfg = load_config()
            assert cfg.cleanup_on_shutdown is True
        finally:
            if original_cleanup is not None:
                os.environ["OPP_MCP_CLEANUP_ON_SHUTDOWN"] = original_cleanup
            else:
                os.environ.pop("OPP_MCP_CLEANUP_ON_SHUTDOWN", None)
            if original_dirs is not None:
                os.environ["OPP_MCP_ALLOWED_DIRS"] = original_dirs
            else:
                os.environ.pop("OPP_MCP_ALLOWED_DIRS", None)
