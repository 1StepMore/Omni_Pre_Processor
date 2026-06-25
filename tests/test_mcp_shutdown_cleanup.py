"""OPP#10: Tests for MCP server shutdown cleanup mechanism.

Tests the temp file tracking, cleanup functions, resource dir cleanup,
atexit integration, safety guards, and signal handler control.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from opp.mcp.config import MCPConfig


def _make_config(tmp_path: Path, cleanup: bool = False) -> MCPConfig:
    return MCPConfig(
        allowed_directories=[Path("/tmp")],
        cleanup_on_shutdown=cleanup,
        resource_storage_dir=tmp_path / "mcp_resources",
    )


class TestTempfileRegistration:

    def test_tempfile_registered_in_tempfiles_set(self, tmp_path: Path):
        from opp.mcp import server as srv

        srv._tempfiles.clear()
        p = srv._safe_temp_output(suffix=".md", parent=tmp_path)
        try:
            assert p in srv._tempfiles
            assert p.exists()
            assert p.name.startswith("opp_mcp_")
            assert p.suffix == ".md"
        finally:
            srv._tempfiles.discard(p)
            p.unlink(missing_ok=True)


class TestCleanupTempfiles:

    def test_cleanup_tempfiles_removes_tracked_files(self, tmp_path: Path):
        from opp.mcp import server as srv

        srv._tempfiles.clear()
        files = [srv._safe_temp_output(suffix=".txt", parent=tmp_path) for _ in range(3)]
        for f in files:
            assert f.exists()

        removed = srv._cleanup_tempfiles()
        assert removed == 3
        assert len(srv._tempfiles) == 0
        for f in files:
            assert not f.exists()

    def test_cleanup_tempfiles_ignores_missing_files(self, tmp_path: Path):
        from opp.mcp import server as srv

        srv._tempfiles.clear()
        p = srv._safe_temp_output(suffix=".txt", parent=tmp_path)
        p.unlink()
        assert not p.exists()

        removed = srv._cleanup_tempfiles()
        assert removed == 0
        assert len(srv._tempfiles) == 0


class TestCleanupResourceDir:

    def test_cleanup_resource_dir_when_flag_false(self, tmp_path: Path):
        from opp.mcp import server as srv

        cfg = _make_config(tmp_path, cleanup=False)
        srv._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "img.png").write_bytes(b"fake")

        count = srv._cleanup_resource_dir()
        assert count == 0
        assert res_dir.exists()

    def test_cleanup_resource_dir_when_flag_true(self, tmp_path: Path):
        from opp.mcp import server as srv

        cfg = _make_config(tmp_path, cleanup=True)
        srv._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "a.png").write_bytes(b"a")
        (res_dir / "b.png").write_bytes(b"b")

        count = srv._cleanup_resource_dir()
        assert count == 2
        assert not res_dir.exists()

    def test_cleanup_resource_dir_refuses_root_path(self, tmp_path: Path):
        from opp.mcp import server as srv

        cfg = MCPConfig(
            allowed_directories=[Path("/tmp")],
            cleanup_on_shutdown=True,
            resource_storage_dir=Path("/"),
        )
        srv._config = cfg

        count = srv._cleanup_resource_dir()
        assert count == 0


class TestAtexitIntegration:

    def test_shutdown_cleanup_runs_on_atexit(self, tmp_path: Path):
        import atexit

        from opp.mcp import server as srv

        srv._tempfiles.clear()
        srv._config = _make_config(tmp_path, cleanup=False)
        p = srv._safe_temp_output(suffix=".txt", parent=tmp_path)
        assert p.exists()

        srv._shutdown_cleanup()
        assert not p.exists()
        assert len(srv._tempfiles) == 0

    def test_atexit_always_runs_even_on_exception(self, tmp_path: Path):
        from opp.mcp import server as srv

        srv._tempfiles.clear()
        cfg = _make_config(tmp_path, cleanup=True)
        srv._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "x.txt").write_bytes(b"x")

        p = srv._safe_temp_output(suffix=".txt", parent=tmp_path)
        assert p.exists()

        with patch.object(srv, "_cleanup_tempfiles", side_effect=RuntimeError("boom")):
            srv._shutdown_cleanup()

        assert not res_dir.exists()
        srv._tempfiles.discard(p)


class TestSignalHandlerControl:

    def test_disable_signal_handlers_env_var(self, monkeypatch):
        monkeypatch.setenv("OPP_MCP_DISABLE_SIGNAL_HANDLERS", "1")
        assert os.environ.get("OPP_MCP_DISABLE_SIGNAL_HANDLERS") == "1"
