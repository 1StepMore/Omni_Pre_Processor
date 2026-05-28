"""Utility for generating images.json structure for ORF's apply_md --images-json parameter."""

import base64
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

    Args:
        result: ExtractionResult containing images
        output_path: Path to write the JSON file

    Returns:
        dict with the images.json structure
    """
    images_list = []

    for img in result.images:
        position = _get_position(img)
        image_entry: dict[str, object] = {
            "paragraph_index": position,
            "mime_type": img.mime_type,
        }

        if img.width is not None:
            image_entry["width"] = img.width
        if img.height is not None:
            image_entry["height"] = img.height

        # Convert bytes data to base64 if data field is available
        if img.data:
            image_entry["data_base64"] = base64.b64encode(img.data).decode("ascii")

        images_list.append(image_entry)

    output = {"images": images_list}

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    return output