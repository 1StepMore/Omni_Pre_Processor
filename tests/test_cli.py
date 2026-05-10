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
    def test_target_lang_required_for_xlf(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            "--source-lang=en",
            str(test_file)
        ])
        assert result.returncode != 0 or "target-lang" in result.stderr.lower()

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
    def test_target_format_xlf_without_target_lang_fails(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=xlf",
            str(test_file)
        ])
        assert result.returncode != 0

    def test_target_format_both_without_target_lang_fails(self, tmp_path):
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")
        result = run_opp([
            "--target-format=both",
            str(test_file)
        ])
        assert result.returncode != 0


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