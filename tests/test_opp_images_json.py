"""Unit tests for OPP images.json generation.

Tests the dict structure produced by generate_images_json() in
opp/utils/images_json.py — no real DOCX extraction needed.

Issue #139 regression coverage lives in TestIssue139ManifestMatchesDisk:
the manifest must mirror every image file the separate-images step wrote
to ``{stem}_images/`` (same relative path the markdown uses), and an
empty manifest with files on disk must never be silent.
"""

import argparse
import json
import logging
from pathlib import Path

from opp.utils.dataclasses import ExtractionResult, ImageData, ParagraphData
from opp.utils.images_json import generate_images_json


class TestGenerateImagesJson:
    """Tests for generate_images_json()."""

    def test_empty_images_list(self, tmp_path: Path):
        """Empty images list produces {"images": [], "total": 0}."""
        result = ExtractionResult(paragraphs=[], tables=[], images=[])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)
        assert output == {"images": [], "total": 0}

        # Verify file was written
        assert output_path.exists()
        with open(output_path) as f:
            parsed = json.load(f)
        assert parsed == {"images": [], "total": 0}

    def test_inline_image_without_dimensions(self, tmp_path: Path):
        """Inline image without width/height has paragraph_index and mime_type only."""
        img = ImageData(
            data=b"fake_png_bytes",
            mime_type="image/png",
            paragraph_index=5,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        entry = output["images"][0]
        assert entry["paragraph_index"] == 5
        assert entry["mime_type"] == "image/png"
        # width/height should NOT be present when None
        assert "width" not in entry
        assert "height" not in entry
        # is_floating should NOT be present for inline images
        assert "is_floating" not in entry

    def test_inline_image_with_dimensions(self, tmp_path: Path):
        """Inline image with explicit width/height includes them."""
        img = ImageData(
            data=b"fake_png",
            mime_type="image/jpeg",
            paragraph_index=3,
            width=800,
            height=600,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        entry = output["images"][0]
        assert entry["paragraph_index"] == 3
        assert entry["width"] == 800
        assert entry["height"] == 600

    def test_floating_image(self, tmp_path: Path):
        """Floating image gets is_floating=true and anchor offsets."""
        img = ImageData(
            data=b"floating_img",
            mime_type="image/png",
            paragraph_index=None,
            is_floating=True,
            wp_anchor_h=1828800,
            wp_anchor_v=2743200,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        entry = output["images"][0]
        assert entry["paragraph_index"] is None
        assert entry["is_floating"] is True
        assert entry["wp_anchor_h"] == 1828800
        assert entry["wp_anchor_v"] == 2743200
        # width/height should NOT be present
        assert "width" not in entry
        assert "height" not in entry

    def test_floating_image_zero_anchors(self, tmp_path: Path):
        """Floating image with zero anchor offsets omits wp_anchor_h/v."""
        img = ImageData(
            data=b"floating_no_offset",
            mime_type="image/png",
            paragraph_index=None,
            is_floating=True,
            wp_anchor_h=0,
            wp_anchor_v=0,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        entry = output["images"][0]
        assert entry["is_floating"] is True
        # 0 offsets are falsy — should be omitted
        assert "wp_anchor_h" not in entry
        assert "wp_anchor_v" not in entry

    def test_mixed_inline_and_floating_images(self, tmp_path: Path):
        """Multiple images of different types are all represented."""
        imgs = [
            ImageData(
                data=b"inline",
                mime_type="image/png",
                paragraph_index=2,
                width=100,
                height=100,
            ),
            ImageData(
                data=b"floating",
                mime_type="image/png",
                paragraph_index=None,
                is_floating=True,
                wp_anchor_h=500000,
                wp_anchor_v=600000,
            ),
        ]
        result = ExtractionResult(paragraphs=[], tables=[], images=imgs)
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        assert len(output["images"]) == 2
        # First image: inline
        assert output["images"][0]["paragraph_index"] == 2
        assert "is_floating" not in output["images"][0]
        # Second image: floating
        assert output["images"][1]["paragraph_index"] is None
        assert output["images"][1]["is_floating"] is True

    def test_data_base64_encoding(self, tmp_path: Path):
        """Image bytes are base64-encoded in data_base64 field."""
        raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\r"  # PNG header
        img = ImageData(
            data=raw_bytes,
            mime_type="image/png",
            paragraph_index=0,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        import base64
        expected_b64 = base64.b64encode(raw_bytes).decode("ascii")
        assert output["images"][0]["data_base64"] == expected_b64
        # Decode back and verify
        decoded = base64.b64decode(output["images"][0]["data_base64"])
        assert decoded == raw_bytes

    def test_position_preference_paragraph_over_page(self, tmp_path: Path):
        """paragraph_index takes priority over page_number."""
        img = ImageData(
            data=b"test",
            mime_type="image/png",
            paragraph_index=42,
            page_number=1,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        assert output["images"][0]["paragraph_index"] == 42

    def test_no_data_field_omits_base64(self, tmp_path: Path):
        """Image with empty data (e.g., temp_path cases) has no data_base64."""
        img = ImageData(
            data=b"",
            mime_type="image/png",
            paragraph_index=0,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        assert "data_base64" not in output["images"][0]

    def test_large_image_dedup_via_temp_path(self, tmp_path: Path):
        """L1-04 TDD RED: images with empty data but same temp_path must be deduplicated.

        Bug: images_json.py:47-48 dedup checks ``if img.data:`` — but for large
        images streamed to disk via temp_path, img.data is b"" (falsy), so the
        dedup is silently skipped. Two identical large images are emitted twice.
        """
        img_file = tmp_path / "large_image.png"
        img_file.write_bytes(b"\x89PNG_FAKE_LARGE_IMAGE_BYTES")

        img1 = ImageData(
            data=b"",
            mime_type="image/png",
            paragraph_index=0,
            temp_path=img_file,
        )
        img2 = ImageData(
            data=b"",
            mime_type="image/png",
            paragraph_index=1,
            temp_path=img_file,
        )
        result = ExtractionResult(paragraphs=[], tables=[], images=[img1, img2])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)

        assert len(output["images"]) == 1, (
            f"L1-04 bug: expected 1 image after dedup of identical temp_path images, "
            f"got {len(output['images'])}. Both images were emitted despite same temp_path."
        )


class TestIssue139ManifestMatchesDisk:
    """Issue #139: images.json claimed zero images while the separate-images
    step had written real files to ``{stem}_images/`` — downstream (OL/ORF)
    concluded "no images" and stripped every markdown image reference.

    Contract after the fix:
    - every image file written by extraction has one manifest entry carrying
      the exact relative path the markdown uses (``file_path``);
    - the manifest keeps the ``images`` list and adds ``total``;
    - an empty manifest with non-empty ``{stem}_images/`` warns by name;
    - a truly image-free document still yields ``{"images": [], "total": 0}``
      from the writer (the CLI path emits no manifest at all for image-free
      documents — that contract is unchanged).
    """

    def test_two_images_total_and_paths_present(self, tmp_path: Path):
        """Writer unit test: 2 image entries → total == 2, both file_path present."""
        imgs = [
            ImageData(
                data=b"image-one-bytes",
                mime_type="image/png",
                paragraph_index=0,
                written_rel_path="./sample_images/sample_image_1.png",
            ),
            ImageData(
                data=b"image-two-bytes",
                mime_type="image/png",
                paragraph_index=1,
                written_rel_path="./sample_images/sample_image_2.png",
            ),
        ]
        result = ExtractionResult(paragraphs=[], tables=[], images=imgs)
        output_path = tmp_path / "sample_images.json"
        output = generate_images_json(result, output_path)

        assert output["total"] == 2
        assert len(output["images"]) == 2
        assert output["images"][0]["file_path"] == "./sample_images/sample_image_1.png"
        assert output["images"][1]["file_path"] == "./sample_images/sample_image_2.png"

        # Schema stability: existing keys are not renamed or dropped
        assert output["images"][0]["paragraph_index"] == 0
        assert output["images"][0]["mime_type"] == "image/png"

        with open(output_path) as f:
            parsed = json.load(f)
        assert parsed["total"] == 2

    def test_manifest_matches_markdown_written_files(self, tmp_path: Path):
        """Regression: files written by the separate-images step must appear
        in the manifest with the same relative path the markdown references."""
        from opp.markdown import MarkdownGenerator

        img = ImageData(
            data=b"\x89PNG\r\n\x1a\n fake image payload",
            mime_type="image/png",
            paragraph_index=0,
        )
        result = ExtractionResult(
            paragraphs=[ParagraphData(text="Hello", position=0, para_index_in_body=0)],
            tables=[],
            images=[img],
        )

        md_path = tmp_path / "sample.md"
        MarkdownGenerator().generate_to_file(result, md_path, embed_images=True)
        md_text = md_path.read_text(encoding="utf-8")

        # Sanity: the file the md references actually exists on disk
        assert "![Image 1](./sample_images/sample_image_1.png)" in md_text
        assert (tmp_path / "sample_images" / "sample_image_1.png").exists()

        output = generate_images_json(result, tmp_path / "sample_images.json")
        assert output["total"] == 1, "manifest must not be empty when files were written"
        entry = output["images"][0]
        assert entry["file_path"] == "./sample_images/sample_image_1.png"
        # Manifest path == the exact markdown reference
        assert f"![Image 1]({entry['file_path']})" in md_text

    def test_duplicate_content_images_each_keep_their_file(self, tmp_path: Path):
        """Regression: two identical images are written to two files, so the
        manifest must list both files (content dedup must not drop a written one)."""
        from opp.markdown import MarkdownGenerator

        payload = b"\x89PNG\r\n\x1a\n identical logo bytes"
        result = ExtractionResult(
            paragraphs=[ParagraphData(text="A", position=0, para_index_in_body=0)],
            tables=[],
            images=[
                ImageData(data=payload, mime_type="image/png"),
                ImageData(data=payload, mime_type="image/png"),
            ],
        )
        MarkdownGenerator().generate_to_file(result, tmp_path / "dup.md", embed_images=True)

        written = sorted(p.name for p in (tmp_path / "dup_images").iterdir())
        assert written == ["dup_image_1.png", "dup_image_2.png"]

        output = generate_images_json(result, tmp_path / "dup_images.json")
        assert output["total"] == 2, (
            f"2 files were written but the manifest lists {output['total']} — "
            f"content dedup must not drop a file that exists on disk"
        )
        assert [e["file_path"] for e in output["images"]] == [
            "./dup_images/dup_image_1.png",
            "./dup_images/dup_image_2.png",
        ]

    def test_rebuilds_from_markdown_when_result_lost_the_images(
        self, tmp_path: Path, caplog
    ):
        """Regression for the reported case: the markdown step wrote image
        files, but the result handed to the writer carries no image entries —
        the manifest must be rebuilt from the markdown refs, not left empty."""
        from opp.markdown import MarkdownGenerator

        result = ExtractionResult(
            paragraphs=[ParagraphData(text="Hello", position=0, para_index_in_body=0)],
            tables=[],
            images=[
                ImageData(
                    data=b"\x89PNG\r\n\x1a\n fake image payload",
                    mime_type="image/png",
                    paragraph_index=0,
                )
            ],
        )
        md_path = tmp_path / "sample.md"
        MarkdownGenerator().generate_to_file(result, md_path, embed_images=True)

        # The collection diverged: no image entries, but the md + files exist.
        diverged = ExtractionResult(paragraphs=result.paragraphs, tables=[], images=[])
        with caplog.at_level(logging.WARNING, logger="opp.utils.images_json"):
            output = generate_images_json(diverged, tmp_path / "sample_images.json")

        assert output["total"] == 1, "empty manifest with files on disk — issue #139"
        entry = output["images"][0]
        assert entry["file_path"] == "./sample_images/sample_image_1.png"
        assert entry["mime_type"] == "image/png"
        assert entry["data_base64"]
        assert "![Image 1](./sample_images/sample_image_1.png)" in md_path.read_text(
            encoding="utf-8"
        )
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("EMPTY" in msg and "sample_images.json" in msg for msg in warnings), (
            f"the rebuild must be reported, not silent: {warnings}"
        )

    def test_empty_manifest_with_files_on_disk_warns(self, tmp_path: Path, caplog):
        """Guard: empty manifest + non-empty {stem}_images/ must warn naming the file.

        Here no markdown exists, so there is nothing to rebuild from — the
        mismatch can only be reported.
        """
        images_dir = tmp_path / "sample_images"
        images_dir.mkdir()
        (images_dir / "sample_image_1.png").write_bytes(b"\x89PNG fake")

        result = ExtractionResult(paragraphs=[], tables=[], images=[])
        with caplog.at_level(logging.WARNING, logger="opp.utils.images_json"):
            output = generate_images_json(result, tmp_path / "sample_images.json")

        assert output == {"images": [], "total": 0}
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("sample_images.json" in msg and "sample_images" in msg for msg in warnings), (
            f"expected an explicit warning naming the empty manifest, got: {warnings}"
        )

    def test_empty_manifest_without_files_no_warning(self, tmp_path: Path, caplog):
        """Guard must stay quiet when no image files exist (truly image-free doc)."""
        result = ExtractionResult(paragraphs=[], tables=[], images=[])
        with caplog.at_level(logging.WARNING, logger="opp.utils.images_json"):
            output = generate_images_json(result, tmp_path / "sample_images.json")

        assert output == {"images": [], "total": 0}
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warnings, f"no warning expected without files on disk, got: {warnings}"


class TestIssue139ExtractGuard:
    """CLI-level behaviour of process_single_file around the manifest: image
    files on disk must always end up in a manifest (or be loudly reported)."""

    @staticmethod
    def _make_args(tmp_path: Path) -> argparse.Namespace:
        return argparse.Namespace(
            target_format="md",
            output_dir=tmp_path / "out",
            no_embed_images=False,
            style_map=None,
            source_lang="en",
            target_lang="zh",
            resource_dir=tmp_path / "resources",
            log_format=None,
            ocr_engine=None,
            ocr_lang=None,
            asr_engine=None,
            model_size=None,
        )

    @staticmethod
    def _make_pipeline(tmp_path: Path, extraction_result: ExtractionResult):
        from opp.detector import FormatType
        from opp.pipeline import OPPPipeline, ProcessingResult

        pipeline = OPPPipeline(tmp_path / "resources")
        proc_result = ProcessingResult(
            content="",
            format_type=FormatType.DOCX,
            images_stored=0,
            extraction_result=extraction_result,
        )
        pipeline.process_file = lambda file_path: proc_result
        return pipeline

    def test_manifest_emitted_when_markdown_references_written_files(
        self, tmp_path: Path, caplog
    ):
        """Reported case: md + image files exist but the result has no image
        entries → the CLI must still emit a manifest matching the md."""
        from opp.commands.extract import process_single_file
        from opp.error_handler import ErrorHandler

        src = tmp_path / "sample.docx"
        src.write_bytes(b"PK\x03\x04 not a real docx - process_file is patched")

        out_dir = tmp_path / "out"
        images_dir = out_dir / "sample_images"
        images_dir.mkdir(parents=True)
        (images_dir / "sample_image_1.png").write_bytes(b"\x89PNG fake")

        empty_result = ExtractionResult(
            paragraphs=[ParagraphData(text="hi", position=0)],
            tables=[],
            images=[],
        )
        pipeline = self._make_pipeline(tmp_path, empty_result)

        def fake_generate_markdown(result, output_path, *a, **kw):
            # Simulates the separate-images step having written the md refs
            # from a collection the result no longer carries.
            Path(output_path).write_text(
                "hi\n\n![Image 1](./sample_images/sample_image_1.png)\n",
                encoding="utf-8",
            )

        pipeline.generate_markdown = fake_generate_markdown
        stats = {"files_processed": 0, "errors": 0}

        with caplog.at_level(logging.WARNING):
            ok = process_single_file(src, self._make_args(tmp_path), pipeline, stats, ErrorHandler())

        assert ok is True
        manifest_path = out_dir / "sample_images.json"
        assert manifest_path.exists(), "files were written — the manifest must exist"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["total"] == 1
        assert manifest["images"][0]["file_path"] == "./sample_images/sample_image_1.png"
        # The artifact is reported in the machine-readable outputs
        assert stats["results"][-1]["outputs"]["images_json"] == str(manifest_path.resolve())
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("EMPTY" in msg and "sample_images.json" in msg for msg in warnings), (
            f"the rebuild must not be silent: {warnings}"
        )

    def test_empty_manifest_and_warning_when_nothing_to_rebuild(
        self, tmp_path: Path, caplog
    ):
        """Files on disk, empty result, markdown without refs (stale dir):
        an empty manifest is emitted and the mismatch is reported."""
        from opp.commands.extract import process_single_file
        from opp.error_handler import ErrorHandler

        src = tmp_path / "sample.docx"
        src.write_bytes(b"PK\x03\x04 not a real docx - process_file is patched")

        out_dir = tmp_path / "out"
        images_dir = out_dir / "sample_images"
        images_dir.mkdir(parents=True)
        (images_dir / "sample_image_1.png").write_bytes(b"\x89PNG fake")

        empty_result = ExtractionResult(
            paragraphs=[ParagraphData(text="hi", position=0)],
            tables=[],
            images=[],
        )
        pipeline = self._make_pipeline(tmp_path, empty_result)
        stats = {"files_processed": 0, "errors": 0}

        with caplog.at_level(logging.WARNING):
            ok = process_single_file(src, self._make_args(tmp_path), pipeline, stats, ErrorHandler())

        assert ok is True
        assert stats["errors"] == 0
        manifest_path = out_dir / "sample_images.json"
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
            "images": [],
            "total": 0,
        }
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("sample_images.json" in msg and "sample_images" in msg for msg in warnings), (
            f"expected the #139 guard warning, got: {warnings}"
        )

    def test_image_free_document_stays_silent(self, tmp_path: Path, caplog):
        """Negative sample: truly image-free document → no manifest, no warning."""
        from opp.commands.extract import process_single_file
        from opp.error_handler import ErrorHandler

        src = tmp_path / "plain.docx"
        src.write_bytes(b"PK\x03\x04 not a real docx - process_file is patched")

        empty_result = ExtractionResult(
            paragraphs=[ParagraphData(text="just text", position=0)],
            tables=[],
            images=[],
        )
        pipeline = self._make_pipeline(tmp_path, empty_result)
        stats = {"files_processed": 0, "errors": 0}

        with caplog.at_level(logging.WARNING):
            ok = process_single_file(src, self._make_args(tmp_path), pipeline, stats, ErrorHandler())

        assert ok is True
        out_dir = tmp_path / "out"
        assert not (out_dir / "plain_images.json").exists()
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warnings, f"no warning expected for an image-free document, got: {warnings}"
