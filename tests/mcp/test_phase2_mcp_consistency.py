"""Tests for Phase 2 MCP consistency changes in OPP (P2-T1, T2, T3, T4).

These tests enforce cross-suite standardization:
- P2-T1: MCP_ALLOWED_DIRECTORIES env var (with OPP_MCP_ALLOWED_DIRS fallback)
- P2-T2: Server name "opp-mcp" (unified naming)
- P2-T3: MCP_TOOL_TIMEOUT env var, default 120s
- P2-T4: MCP_ALLOWED_EXTENSIONS env var override
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# P2-T1: Unified env var
# ---------------------------------------------------------------------------

def test_p2_t1_mcp_allowed_directories_is_primary():
    """MCP_ALLOWED_DIRECTORIES env var should be the primary for allowed dirs."""
    env = os.environ.copy()
    env["MCP_ALLOWED_DIRECTORIES"] = "/tmp/unified"
    env.pop("OPP_MCP_ALLOWED_DIRS", None)
    result = subprocess.run(
        [sys.executable, "-c",
         "from opp.mcp.config import load_config; "
         "c = load_config(); "
         "print(','.join(str(d) for d in c.allowed_directories))"],
        capture_output=True, text=True, timeout=30,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),  # OPP root
    )
    assert "/tmp/unified" in result.stdout, (
        f"MCP_ALLOWED_DIRECTORIES not read as primary: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_p2_t1_opp_fallback_still_works():
    """Backward compat: OPP_MCP_ALLOWED_DIRS should still work when unified is unset."""
    env = os.environ.copy()
    env["OPP_MCP_ALLOWED_DIRS"] = "/tmp/legacy"
    env.pop("MCP_ALLOWED_DIRECTORIES", None)
    result = subprocess.run(
        [sys.executable, "-c",
         "from opp.mcp.config import load_config; "
         "c = load_config(); "
         "print(','.join(str(d) for d in c.allowed_directories))"],
        capture_output=True, text=True, timeout=30,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert "/tmp/legacy" in result.stdout, (
        f"OPP_MCP_ALLOWED_DIRS fallback broken: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# P2-T2: Server name
# ---------------------------------------------------------------------------

def test_p2_t2_server_name_is_opp_mcp():
    """OPP MCP server should be named 'opp-mcp'."""
    from opp.mcp.server import server
    assert server.name == "opp-mcp", (
        f"Server name is '{server.name}', expected 'opp-mcp'"
    )


# ---------------------------------------------------------------------------
# P2-T3: Timeout
# ---------------------------------------------------------------------------

def test_p2_t3_default_timeout_is_120():
    """Default request_timeout_seconds should be 120."""
    env = os.environ.copy()
    env.pop("MCP_TOOL_TIMEOUT", None)
    env.pop("OPP_MCP_TIMEOUT", None)
    env["OPP_MCP_ALLOWED_DIRS"] = "/tmp"
    result = subprocess.run(
        [sys.executable, "-c",
         "from opp.mcp.config import load_config; "
         "c = load_config(); "
         "print(c.request_timeout_seconds)"],
        capture_output=True, text=True, timeout=30,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert result.stdout.strip() == "120", (
        f"Default timeout is {result.stdout.strip()}, expected 120: "
        f"stderr={result.stderr!r}"
    )


def test_p2_t3_mcp_tool_timeout_env_var_works():
    """MCP_TOOL_TIMEOUT env var should override the default timeout."""
    env = os.environ.copy()
    env["MCP_TOOL_TIMEOUT"] = "90"
    env.pop("OPP_MCP_TIMEOUT", None)
    env["OPP_MCP_ALLOWED_DIRS"] = "/tmp"
    result = subprocess.run(
        [sys.executable, "-c",
         "from opp.mcp.config import load_config; "
         "c = load_config(); "
         "print(c.request_timeout_seconds)"],
        capture_output=True, text=True, timeout=30,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert result.stdout.strip() == "90", (
        f"MCP_TOOL_TIMEOUT not read: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# P2-T4: Allowed extensions env var
# ---------------------------------------------------------------------------

def test_p2_t4_mcp_allowed_extensions_env_var():
    """MCP_ALLOWED_EXTENSIONS env var should override the default set."""
    import tempfile
    from pathlib import Path
    from opp.mcp.security import PathValidator

    with tempfile.NamedTemporaryFile(suffix=".custom", delete=False) as f:
        custom_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        pptx_path = f.name
    try:
        os.environ["MCP_ALLOWED_EXTENSIONS"] = ".md,.docx,.custom"
        validator = PathValidator(allowed_directories=[Path("/tmp")])
        result = validator.validate_path(custom_path)
        assert result.success, (
            f"Custom extension .custom from MCP_ALLOWED_EXTENSIONS not accepted: {result.error}"
        )
        # Ensure .pptx (in default but not in override) is rejected
        result2 = validator.validate_path(pptx_path)
        assert not result2.success, (
            ".pptx should be rejected when MCP_ALLOWED_EXTENSIONS overrides defaults"
        )
    finally:
        os.environ.pop("MCP_ALLOWED_EXTENSIONS", None)
        os.unlink(custom_path)
        os.unlink(pptx_path)
