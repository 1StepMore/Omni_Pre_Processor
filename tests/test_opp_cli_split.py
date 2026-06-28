"""Regression tests for OPP CLI split (Task 3.7).

Verifies that after splitting ``cli.py`` into smaller modules, the CLI
still works correctly. These tests use in-process invocation so they
are fast and isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ── Import-based regression tests ──────────────────────────────────────


class TestModuleImports:
    """Every public name from the original cli.py is still importable."""

    def test_main_exists(self):
        from opp.cli import main
        assert callable(main)

    def test_create_parser_exists(self):
        from opp.cli import create_parser
        assert callable(create_parser)

    def test_process_single_file_exists(self):
        from opp.cli import process_single_file
        assert callable(process_single_file)

    def test_batch_process_exists(self):
        from opp.cli import batch_process
        assert callable(batch_process)

    def test_start_mcp_exists(self):
        from opp.cli import start_mcp
        assert callable(start_mcp)

    def test_utils_importable(self):
        """All utility functions from the original cli.py are re-exported."""
        from opp.cli import (
            _cache_root, _cache_key, _relevant_config_for_cache,
            _check_cache, _write_cache, _clear_opp_cache,
            _load_env_for_opp, _load_dotenv_for_opp,
            get_supported_extensions, expand_directories,
            _detect_format_from_extension, _compute_file_md5,
            _count_xliff_units, get_opp_version,
        )
        assert callable(_cache_root)
        assert callable(_clear_opp_cache)
        assert callable(get_opp_version)

    def test_submodule_imports(self):
        """New submodules can be imported directly."""
        import opp.cliutils
        assert hasattr(opp.cliutils, "_cache_root")

        from opp.commands.extract import process_single_file
        assert callable(process_single_file)

        from opp.commands.batch import batch_process
        assert callable(batch_process)

        from opp.commands.mcp import start_mcp
        assert callable(start_mcp)


# ── CLI smoke tests (in-process, fast) ─────────────────────────────────


class TestCLISmoke:
    """Verifies CLI entry points work correctly."""

    def test_create_parser_returns_parser(self):
        from opp.cli import create_parser
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "opp"

    def test_help_includes_target_format(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--target-format" in help_text

    def test_help_includes_source_lang(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--source-lang" in help_text

    def test_help_includes_target_lang(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--target-lang" in help_text

    def test_help_includes_output_dir(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--output-dir" in help_text

    def test_help_includes_detect_format(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--detect-format" in help_text

    def test_help_includes_resource_dir(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--resource-dir" in help_text

    def test_help_includes_report(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--report" in help_text

    def test_help_includes_batch(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--batch" in help_text

    def test_help_includes_ocr_options(self):
        from opp.cli import create_parser
        help_text = create_parser().format_help()
        assert "--ocr-engine" in help_text
        assert "--ocr-lang" in help_text

    def test_main_returns_int_with_missing_args(self):
        """Invoking main() with --help should print help and exit 0."""
        from opp.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

    def test_target_lang_required_for_xlf(self):
        """--target-format xlf without --target-lang should fail."""
        from opp.cli import main
        with pytest.raises(SystemExit):
            main(["--target-format", "xlf", "dummy.docx"])

    def test_target_lang_required_for_both(self):
        """--target-format both without --target-lang should fail."""
        from opp.cli import main
        with pytest.raises(SystemExit):
            main(["--target-format", "both", "dummy.docx"])

    def test_clear_cache_flag(self, tmp_path, monkeypatch):
        """--clear-cache should complete successfully."""
        monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
        from opp.cli import main
        dummy = tmp_path / "dummy.txt"
        dummy.write_text("x")
        rc = main(["--clear-cache", str(dummy)])
        assert rc == 0


# ── New sub-module tests ───────────────────────────────────────────────


class TestCliutilsModule:
    """Tests for opp.cliutils functions."""

    def test_get_supported_extensions(self):
        from opp.cliutils import get_supported_extensions
        exts = get_supported_extensions()
        assert ".docx" in exts
        assert ".pdf" in exts
        assert isinstance(exts, list)

    def test_get_opp_version(self):
        from opp.cliutils import get_opp_version
        ver = get_opp_version()
        assert isinstance(ver, str)
        assert ver

    def test_expand_directories_with_file(self, tmp_path):
        from opp.cliutils import expand_directories
        f = tmp_path / "test.docx"
        f.write_bytes(b"PK\x03\x04")
        result = expand_directories([f])
        assert len(result) == 1
        assert result[0] == f

    def test_clear_cache_returns_zero_when_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "nocache"))
        from opp.cliutils import _clear_opp_cache
        assert _clear_opp_cache() == 0

    def test_write_and_check_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
        from opp.cliutils import _write_cache, _check_cache, _cache_root
        from argparse import Namespace

        src = tmp_path / "input.txt"
        src.write_text("hello")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        args = Namespace(config=None, no_cache=False)
        _write_cache(src, args, out_dir)
        # No xlf file was written, so cache miss is expected
        assert _check_cache(src, args, out_dir) is False

    def test_load_dotenv(self, tmp_path):
        from opp.cliutils import _load_dotenv_for_opp
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_OPP_SPLIT=ok")
        _load_dotenv_for_opp(env_file)
        import os
        assert os.environ.get("TEST_OPP_SPLIT") == "ok"

    def test_detect_format_from_extension(self):
        from opp.cliutils import _detect_format_from_extension
        assert _detect_format_from_extension(Path("test.docx")) == "DOCX"
        assert _detect_format_from_extension(Path("test.pdf")) == "PDF"
        assert _detect_format_from_extension(Path("test.unknown")) == "UNKNOWN"

    def test_compute_file_md5(self, tmp_path):
        from opp.cliutils import _compute_file_md5
        f = tmp_path / "test.txt"
        f.write_text("hello")
        md5 = _compute_file_md5(f)
        assert len(md5) == 32
        assert isinstance(md5, str)
