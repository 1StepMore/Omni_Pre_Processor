"""Utility for generating images.json structure for ORF's apply_md --images-json parameter."""

import base64
import hashlib
import json
from pathlib import Path

from opp.utils.dataclasses import ExtractionResult, ImageData


def _get_position(img: ImageData) -> int | None:
    """Get the position index from the first non-None position field."""
    if img.paragraph_index is not None:
        return img.paragraph_index
    if img.page_number is not None:
        return img.page_number
    if img.slide_index is not None:
        return img.slide_index
    if img.element_index is not None:
        return img.element_index
    if img.spine_index is not None:
        return img.spine_index
    return None


def generate_images_json(result: ExtractionResult, output_path: Path) -> dict:
    """
    Generate images.json structure from ExtractionResult.

    Deduplicates images by MD5 content hash to prevent identical images
    (e.g. same icon appearing in multiple paragraphs) from being emitted
    multiple times.

    Args:
        result: ExtractionResult containing images
        output_path: Path to write the JSON file

    Returns:
        dict with the images.json structure
    """
    seen_content_hashes: set[str] = set()
    images_list = []

    for img in result.images:
        content_hash = None
        if img.data:
            content_hash = hashlib.md5(img.data).hexdigest()
        elif img.temp_path is not None and img.temp_path.exists():
            hasher = hashlib.md5()
            with open(img.temp_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            content_hash = hasher.hexdigest()

        if content_hash is not None:
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)

        position = _get_position(img)
        image_entry: dict[str, object] = {
            "paragraph_index": position,
            "mime_type": img.mime_type,
        }

        if getattr(img, "is_floating", False):
            image_entry["is_floating"] = True
            anchor_h = getattr(img, "wp_anchor_h", 0)
            anchor_v = getattr(img, "wp_anchor_v", 0)
            if anchor_h:
                image_entry["wp_anchor_h"] = anchor_h
            if anchor_v:
                image_entry["wp_anchor_v"] = anchor_v

        if img.width is not None:
            image_entry["width"] = img.width
        if img.height is not None:
            image_entry["height"] = img.height

        if img.data:
            image_entry["data_base64"] = base64.b64encode(img.data).decode("ascii")

        images_list.append(image_entry)

    output = {"images": images_list}

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    return output