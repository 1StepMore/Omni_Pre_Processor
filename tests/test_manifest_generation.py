import json
import subprocess
import sys
from pathlib import Path

import pytest

from opp.pipeline import OPPPipeline


# Use the unified suite venv (Python 3.13, all 3 modules installed in editable mode)
# The deprecated Omni_Pre_Processor/.venv (Python 3.12) no longer has OPP installed.
VENV_PYTHON = sys.executable


def run_opp(args: list, tmp_path: Path) -> subprocess.CompletedProcess:
    # Always pass --no-cache so repeated test invocations (and other test files
    # that share the same input content) don't get served from OPP's content-hash
    # cache, which would skip manifest generation.
    if "--no-cache" not in args:
        args = ["--no-cache"] + args
    cmd = [VENV_PYTHON, "-m", "opp.cli"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )


class TestManifestGeneration:
    """Tests for manifest.json generation during output creation."""

    def test_manifest_generates_for_md_output(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"
        assert manifest_path.stat().st_size > 0, "Manifest file is empty"

    def test_manifest_generates_for_xlf_output(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=xlf",
            "--source-lang=en",
            "--target-lang=zh",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"
        assert manifest_path.stat().st_size > 0, "Manifest file is empty"

    def test_manifest_captures_source_info(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "source" in manifest, "Manifest missing 'source' key"
        source = manifest["source"]

        assert "file_path" in source, "Source missing 'file_path'"
        assert "test.csv" in source["file_path"], "file_path does not contain original filename"

        assert "original_filename" in source, "Source missing 'original_filename'"
        assert source["original_filename"] == "test.csv", "original_filename incorrect"

        assert "format" in source, "Source missing 'format'"
        assert source["format"] == "CSV", "format should be CSV"

        assert "file_size_bytes" in source, "Source missing 'file_size_bytes'"
        assert source["file_size_bytes"] > 0, "file_size_bytes should be > 0"

        assert "file_hash_md5" in source, "Source missing 'file_hash_md5'"
        assert len(source["file_hash_md5"]) == 32, "MD5 hash should be 32 characters"

    def test_manifest_captures_extraction_outputs(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "extraction" in manifest, "Manifest missing 'extraction' key"
        extraction = manifest["extraction"]

        assert "outputs" in extraction, "Extraction missing 'outputs' key"
        outputs = extraction["outputs"]

        assert "markdown" in outputs, "Outputs missing 'markdown' key"
        md_output = outputs["markdown"]

        assert "path" in md_output, "Markdown output missing 'path'"
        assert ".md" in md_output["path"], "Markdown path should contain .md extension"

        assert "paragraph_count" in md_output, "Markdown output missing 'paragraph_count'"
        assert md_output["paragraph_count"] >= 0, "paragraph_count should be >= 0"

        assert "table_count" in md_output, "Markdown output missing 'table_count'"

    def test_manifest_captures_image_info(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "extraction" in manifest, "Manifest missing 'extraction' key"
        extraction = manifest["extraction"]

        assert "images" in extraction, "Extraction missing 'images' key"
        images = extraction["images"]

        assert isinstance(images, list), "images should be a list"

    def test_manifest_captures_warnings(self, tmp_path: Path):
        from csv import writer
        
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["Header1", "Header2"])
            w.writerow(["Data1", "Data2"])

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_opp([
            "--target-format=md",
            "--output-dir", str(output_dir),
            str(csv_file)
        ], tmp_path)

        manifest_path = output_dir / "test_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "extraction" in manifest, "Manifest missing 'extraction' key"
        extraction = manifest["extraction"]

        assert "warnings" in extraction, "Extraction missing 'warnings' key"
        warnings = extraction["warnings"]

        assert isinstance(warnings, list), "warnings should be a list"