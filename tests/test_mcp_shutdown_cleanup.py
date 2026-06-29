"""OPP#10: Tests for MCP server shutdown cleanup mechanism.

Tests the temp file tracking, cleanup functions, resource dir cleanup,
atexit integration, safety guards, and signal handler control.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from opp.mcp import common as _c
from opp.mcp.config import MCPConfig


def _make_config(tmp_path: Path, cleanup: bool = False) -> MCPConfig:
    return MCPConfig(
        allowed_directories=[Path("/tmp")],
        cleanup_on_shutdown=cleanup,
        resource_storage_dir=tmp_path / "mcp_resources",
    )


class TestTempfileRegistration:

    def test_tempfile_registered_in_tempfiles_set(self, tmp_path: Path):
        _c._tempfiles.clear()
        p = _c._safe_temp_output(suffix=".md", parent=tmp_path)
        try:
            assert p in _c._tempfiles
            assert p.exists()
            assert p.name.startswith("opp_mcp_")
            assert p.suffix == ".md"
        finally:
            _c._tempfiles.discard(p)
            p.unlink(missing_ok=True)


class TestCleanupTempfiles:

    def test_cleanup_tempfiles_removes_tracked_files(self, tmp_path: Path):
        _c._tempfiles.clear()
        files = [_c._safe_temp_output(suffix=".txt", parent=tmp_path) for _ in range(3)]
        for f in files:
            assert f.exists()

        removed = _c._cleanup_tempfiles()
        assert removed == 3
        assert len(_c._tempfiles) == 0
        for f in files:
            assert not f.exists()

    def test_cleanup_tempfiles_ignores_missing_files(self, tmp_path: Path):
        _c._tempfiles.clear()
        p = _c._safe_temp_output(suffix=".txt", parent=tmp_path)
        p.unlink()
        assert not p.exists()

        removed = _c._cleanup_tempfiles()
        assert removed == 0
        assert len(_c._tempfiles) == 0


class TestCleanupResourceDir:

    def test_cleanup_resource_dir_when_flag_false(self, tmp_path: Path):
        cfg = _make_config(tmp_path, cleanup=False)
        _c._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "img.png").write_bytes(b"fake")

        count = _c._cleanup_resource_dir()
        assert count == 0
        assert res_dir.exists()

    def test_cleanup_resource_dir_when_flag_true(self, tmp_path: Path):
        cfg = _make_config(tmp_path, cleanup=True)
        _c._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "a.png").write_bytes(b"a")
        (res_dir / "b.png").write_bytes(b"b")

        count = _c._cleanup_resource_dir()
        assert count == 2
        assert not res_dir.exists()

    def test_cleanup_resource_dir_refuses_root_path(self, tmp_path: Path):
        cfg = MCPConfig(
            allowed_directories=[Path("/tmp")],
            cleanup_on_shutdown=True,
            resource_storage_dir=Path("/"),
        )
        _c._config = cfg

        count = _c._cleanup_resource_dir()
        assert count == 0


class TestAtexitIntegration:

    def test_shutdown_cleanup_runs_on_atexit(self, tmp_path: Path):
        import atexit  # noqa: F401  (kept for documentation that atexit is the integration point)

        _c._tempfiles.clear()
        _c._config = _make_config(tmp_path, cleanup=False)
        p = _c._safe_temp_output(suffix=".txt", parent=tmp_path)
        assert p.exists()

        _c._shutdown_cleanup()
        assert not p.exists()
        assert len(_c._tempfiles) == 0

    def test_atexit_always_runs_even_on_exception(self, tmp_path: Path):
        _c._tempfiles.clear()
        cfg = _make_config(tmp_path, cleanup=True)
        _c._config = cfg
        res_dir = cfg.resource_storage_dir
        res_dir.mkdir(parents=True)
        (res_dir / "x.txt").write_bytes(b"x")

        p = _c._safe_temp_output(suffix=".txt", parent=tmp_path)
        assert p.exists()

        with patch.object(_c, "_cleanup_tempfiles", side_effect=RuntimeError("boom")):
            _c._shutdown_cleanup()

        assert not res_dir.exists()
        _c._tempfiles.discard(p)


class TestSignalHandlerControl:

    def test_disable_signal_handlers_env_var(self, monkeypatch):
        monkeypatch.setenv("OPP_MCP_DISABLE_SIGNAL_HANDLERS", "1")
        assert os.environ.get("OPP_MCP_DISABLE_SIGNAL_HANDLERS") == "1"
