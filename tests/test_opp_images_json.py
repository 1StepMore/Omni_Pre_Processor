"""Unit tests for OPP images.json generation.

Tests the dict structure produced by generate_images_json() in
opp/utils/images_json.py — no real DOCX extraction needed.
"""

import json
from pathlib import Path

from opp.utils.images_json import generate_images_json
from opp.utils.dataclasses import ExtractionResult, ImageData


class TestGenerateImagesJson:
    """Tests for generate_images_json()."""

    def test_empty_images_list(self, tmp_path: Path):
        """Empty images list produces {"images": []}."""
        result = ExtractionResult(paragraphs=[], tables=[], images=[])
        output_path = tmp_path / "images.json"
        output = generate_images_json(result, output_path)
        assert output == {"images": []}

        # Verify file was written
        assert output_path.exists()
        with open(output_path) as f:
            parsed = json.load(f)
        assert parsed == {"images": []}

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
