"""Unit tests for OPP CLI."""

import subprocess
import sys
from pathlib import Path

import pytest


def run_opp(args_list, **kwargs):
    args_str = str(args_list)
    cmd = f"import sys; sys.argv = ['opp'] + {args_str}; from opp.cli import main; main()"
    result = subprocess.run(
        [sys.executable, "-c", cmd],
        capture_output=True,
        text=True,
        **kwargs
    )
    return result


class TestTargetFormatFlag:
    def test_target_format_md_accepted(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp(["--target-format=md", str(test_file)])
        assert result.returncode == 0 or "error" not in result.stderr.lower()

    def test_target_format_xlf_accepted(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            "--source-lang=en",
            "--target-lang=fr",
            str(test_file)
        ])
        assert result.returncode == 0 or "error" not in result.stderr.lower()

    def test_target_format_both_accepted(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=both",
            "--source-lang=en",
            "--target-lang=fr",
            str(test_file)
        ])
        assert result.returncode == 0 or "error" not in result.stderr.lower()


class TestSourceLangFlag:
    def test_source_lang_custom_value(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=md",
            "--source-lang=de",
            str(test_file)
        ])
        assert result.returncode == 0 or "error" not in result.stderr.lower()

    def test_source_lang_default_is_en(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp(["--target-format=md", str(test_file)])
        assert result.returncode == 0


class TestTargetLangFlag:
    def test_target_lang_is_required_for_xlf(self, tmp_path):
        """OPP CLI now REQUIRES --target-lang when --target-format is xlf or both.

        Previously the default was 'en' and the validation check never fired
        because 'en' is truthy. We changed the default to None so the
        requirement check at cli.py:467 can enforce it. This test pins the
        new contract: the CLI exits with a non-zero code and a clear error
        message when --target-lang is missing.
        """
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            "--source-lang=zh",
            str(test_file)
        ])
        assert result.returncode != 0
        assert "target-lang is required" in result.stderr.lower()

    def test_target_lang_works_when_provided(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            "--source-lang=en",
            "--target-lang=zh",
            str(test_file)
        ])
        assert result.returncode == 0 or "error" not in result.stderr.lower()


class TestOutputDirFlag:
    def test_output_dir_redirects_output(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        result = run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(test_file)
        ])
        assert result.returncode == 0 or "error" not in result.stderr.lower()


class TestValidation:
    def test_target_format_xlf_requires_target_lang(self, tmp_path):
        """OPP CLI now REQUIRES --target-lang when --target-format is xlf.

        This test pins the new contract: the CLI exits with a non-zero
        code and a clear error message when --target-lang is missing.
        See TestTargetLangFlag.test_target_lang_is_required_for_xlf.
        """
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            str(test_file)
        ])
        assert result.returncode != 0
        assert "target-lang is required" in result.stderr.lower()

    def test_target_format_both_requires_target_lang(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=both",
            str(test_file)
        ])
        assert result.returncode != 0
        assert "target-lang is required" in result.stderr.lower()


class TestExistingFlagsRegression:
    def test_detect_format_flag_works(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp(["--detect-format", str(test_file)])
        assert result.returncode == 0

    def test_resource_dir_flag_works(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        resource_dir = tmp_path / "resources"
        result = run_opp([
            "--resource-dir", str(resource_dir),
            str(test_file)
        ])
        assert result.returncode == 0

    def test_report_flag_works(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp(["--report", "text", str(test_file)])
        assert result.returncode == 0

    def test_batch_flag_works(self, tmp_path):
        test_file1 = tmp_path / "test1.docx"
        test_file2 = tmp_path / "test2.docx"
        test_file1.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        test_file2.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp(["--batch", str(test_file1), str(test_file2)])
        assert result.returncode == 0


class TestHelpOutput:
    def test_help_shows_target_format(self):
        result = run_opp(["--help"])
        assert "--target-format" in result.stdout

    def test_help_shows_source_lang(self):
        result = run_opp(["--help"])
        assert "--source-lang" in result.stdout

    def test_help_shows_target_lang(self):
        result = run_opp(["--help"])
        assert "--target-lang" in result.stdout

    def test_help_shows_output_dir(self):
        result = run_opp(["--help"])
        assert "--output-dir" in result.stdout
    def test_resource_dir_rejects_prefix_sibling_escape(self, tmp_path, monkeypatch):
        """ADR 0007 Phase 2B-lite regression: `startswith` containment used to
        accept `<allow>-evil` as inside `<allow>`; component-wise containment
        (Path.is_relative_to) must reject it. tempfile.gettempdir is pinned so
        the /tmp fallback umbrella cannot mask the sibling case."""
        import tempfile

        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        allow = tmp_path / "allow"
        allow.mkdir()
        evil = tmp_path / "allow-evil"
        evil.mkdir()
        # point the tempdir umbrella AWAY from the allow/allow-evil pair so
        # gettempdir() cannot cover the sibling case
        monkeypatch.setattr(
            tempfile, "gettempdir", lambda: str(tmp_path / "othertmp")
        )
        monkeypatch.setenv("OPP_ALLOWED_DIRECTORIES", str(allow))
        from opp.cli import main

        with pytest.raises(SystemExit) as excinfo:
            main(["--resource-dir", str(evil), str(test_file)])
        assert excinfo.value.code == 2, (
            "a prefix-sibling of an allowed dir must be rejected (component-wise "
            "containment), not accepted by the string-prefix test"
        )
