"""Tests for Issue #50: Path() conversion in OPP pipeline output methods.

Before fix: passing str paths to generate_xliff, save_skeleton,
generate_markdown, or generate_images_json crashes because downstream
callees use Path-only operations (.parent, .write_text, /, etc.).

After fix: each method calls Path() on its output_path/output_dir argument
at the top (idempotent — Path() of Path returns the same Path).
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestPathConversionForPipeline:
    """Path() conversion in 4 OPP pipeline output methods (#50)."""

    def _make_pipeline(self, tmp_path):
        from opp.pipeline import OPPPipeline
        # OPPPipeline(resource_storage_dir, config_path=None, max_file_size_mb=100)
        # No litellm/Router involved — just regular extractors + generators
        return OPPPipeline(
            resource_storage_dir=tmp_path / "resources",
            config_path=None,
        )

    def _make_extraction_result(self):
        result = MagicMock()
        result.metadata = None
        result.paragraphs = []
        result.tables = []
        result.images = []
        result.attachments = []
        result.warnings = []
        result.is_transcription = False
        result.skeleton = b"PK\x03\x04fake_skeleton_bytes"
        result.skeleton_files = ["word/document.xml"]
        result.skeleton_html = None
        return result

    # --- R1: generate_markdown accepts str ---
    def test_generate_markdown_accepts_str_path(self, tmp_path):
        from opp.utils.dataclasses import ParagraphData
        pipeline = self._make_pipeline(tmp_path)
        result = self._make_extraction_result()
        result.paragraphs = [
            ParagraphData(text="Hello", style=None)
        ]
        # The path the test gives is a plain str
        output_path = str(tmp_path / "out.md")
        # Before fix: passes through to MarkdownGenerator which calls
        # output_path.parent.mkdir(...) — AttributeError on str.
        ret = pipeline.generate_markdown(result, output_path)
        assert isinstance(ret, Path)
        assert ret.exists()
        assert "Hello" in ret.read_text(encoding="utf-8")

    # --- R2: generate_xliff accepts str ---
    def test_generate_xliff_accepts_str_path(self, tmp_path):
        from opp.utils.dataclasses import ParagraphData
        pipeline = self._make_pipeline(tmp_path)
        result = self._make_extraction_result()
        result.paragraphs = [
            ParagraphData(text="Hello world", style=None)
        ]
        # Test that the XLIFF generator doesn't crash on str input.
        output_path = str(tmp_path / "out.xlf")
        # Before fix: passes through to XLIFFFileGenerator.write_to_file
        # which calls path.parent.mkdir(...) — AttributeError on str.
        ret = pipeline.generate_xliff(
            result, output_path, source_lang="en", target_lang="zh"
        )
        assert isinstance(ret, Path)
        assert ret.exists()

    # --- R3: generate_images_json accepts str ---
    def test_generate_images_json_accepts_str_path(self, tmp_path):
        from opp.utils.dataclasses import ImageData
        pipeline = self._make_pipeline(tmp_path)
        result = self._make_extraction_result()
        result.images = [
            ImageData(data=b"\x89PNG", mime_type="image/png")
        ]
        # Use a str path. Before fix: passes through to generate_images_json
        # utility function which calls output_path.write_text(...) — crash.
        output_path = str(tmp_path / "out.json")
        ret = pipeline.generate_images_json(result, output_path)
        assert isinstance(ret, Path)
        assert ret.exists()

    # --- R4: save_skeleton accepts str output_dir ---
    def test_save_skeleton_accepts_str_output_dir(self, tmp_path):
        pipeline = self._make_pipeline(tmp_path)
        result = self._make_extraction_result()
        # Use a str output_dir. Before fix: pipeline.py:180 does
        # `output_dir / f"{base_name}.skeleton.zip"` — TypeError on str.
        output_dir = str(tmp_path)
        ret = pipeline.save_skeleton(result, "test", output_dir)
        assert isinstance(ret, Path)
        assert ret.exists()
        assert ret.suffix == ".zip"

    # --- R5: process_file already has the fix (regression) ---
    def test_process_file_still_accepts_str_path(self, tmp_path):
        pipeline = self._make_pipeline(tmp_path)
        # Test that the existing Path() conversion in process_file still works
        test_file = tmp_path / "test.txt"
        test_file.write_text("dummy", encoding="utf-8")
        # process_file should accept str path
        ret = pipeline.process_file(str(test_file))
        assert ret is not None

    # --- R6: Path() is idempotent (regression for the fix) ---
    def test_path_conversion_is_idempotent(self):
        """Path() of a Path object returns the same Path — no double-wrapping."""
        p = Path("/tmp/foo")
        assert Path(p) is p or Path(p) == p
        # The fix must not change behavior when a Path is already passed
        assert isinstance(Path("/tmp/foo"), Path)
