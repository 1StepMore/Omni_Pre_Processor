"""Utility for generating images.json structure for ORF's apply_md --images-json parameter."""

import base64
import hashlib
import json
import logging
import re
from pathlib import Path

from opp.utils.dataclasses import ExtractionResult, ImageData

logger = logging.getLogger(__name__)

# Markdown image reference, e.g. ``![Image 1](./sample_images/sample_image_1.png)``.
_IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")


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


def _sibling_images_dir(output_path: Path) -> Path | None:
    """Return the ``{stem}_images/`` directory next to a ``{stem}_images.json`` manifest, if any.

    Used by the empty-manifest recovery/warning (issue #139): when the
    manifest would come out empty but image files were written next to it,
    that mismatch must never be silent.
    """
    stem = output_path.stem
    if not stem.endswith("_images"):
        return None
    base_stem = stem[: -len("_images")]
    if not base_stem:
        return None
    return output_path.parent / f"{base_stem}_images"


def _sibling_markdown_path(output_path: Path) -> Path | None:
    """Return the ``{stem}.md`` file next to a ``{stem}_images.json`` manifest, if any."""
    images_dir = _sibling_images_dir(output_path)
    if images_dir is None:
        return None
    base_stem = images_dir.name[: -len("_images")]
    return output_path.parent / f"{base_stem}.md"


def markdown_image_refs(output_path: Path) -> list[str]:
    """Return the image paths the emitted markdown references from ``{stem}_images/``.

    These are the relative paths exactly as they appear in the markdown
    (``./sample_images/sample_image_1.png``), in document order and
    de-duplicated. Empty when the markdown is missing or references no
    image in the sibling directory.

    Issue #139: this is the ground truth the manifest must mirror — a
    manifest entry per markdown reference, no more and no less.
    """
    images_dir = _sibling_images_dir(output_path)
    md_path = _sibling_markdown_path(output_path)
    if images_dir is None or md_path is None or not md_path.is_file():
        return []

    try:
        md_text = md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    prefix = f"./{images_dir.name}/"
    refs: list[str] = []
    seen: set[str] = set()
    for match in _IMAGE_REF.finditer(md_text):
        ref = match.group(1)
        if not ref.startswith(prefix) or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


_MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "svg": "image/svg+xml",
}


def _entries_from_markdown(output_path: Path) -> list[dict]:
    """Rebuild manifest entries from the image references the markdown uses.

    Issue #139 fallback: files were written to ``{stem}_images/`` but the
    ``ExtractionResult`` handed to the writer carries no image entries (the
    collections diverged). The markdown is the authoritative record of what
    was written and referenced, so derive one entry per reference. Only files
    that still exist on disk are emitted; a stale reference is skipped.
    """
    images_dir = _sibling_images_dir(output_path)
    if images_dir is None:
        return []

    entries: list[dict] = []
    for ref in markdown_image_refs(output_path):
        img_path = output_path.parent / ref
        if not img_path.is_file():
            continue
        suffix = img_path.suffix.lstrip(".").lower()
        mime_type = _MIME_BY_EXT.get(suffix) or (f"image/{suffix}" if suffix else "application/octet-stream")
        entry: dict[str, object] = {
            "paragraph_index": None,
            "mime_type": mime_type,
            "file_path": ref,
        }
        try:
            entry["data_base64"] = base64.b64encode(img_path.read_bytes()).decode("ascii")
        except OSError as e:
            logger.warning("Could not read image %s for images.json: %s", img_path, e)
        entries.append(entry)
    return entries


def _warn_on_empty_manifest(output_path: Path) -> None:
    """Log an explicit warning when the manifest is empty but image files exist on disk (issue #139)."""
    images_dir = _sibling_images_dir(output_path)
    if images_dir is not None and images_dir.is_dir() and any(images_dir.iterdir()):
        logger.warning(
            "images.json manifest %s is EMPTY but image files exist in %s — "
            "downstream consumers (OL/ORF) will treat this document as image-free "
            "and drop the references",
            output_path,
            images_dir,
        )


def generate_images_json(result: ExtractionResult, output_path: Path) -> dict:
    """
    Generate images.json structure from ExtractionResult.

    Deduplicates images by MD5 content hash to prevent identical images
    (e.g. same icon appearing in multiple paragraphs) from being emitted
    multiple times. Images that the markdown step actually wrote to disk are
    never deduplicated away: each written file gets its own entry so the
    manifest always matches ``{stem}_images/`` (issue #139).

    Args:
        result: ExtractionResult containing images
        output_path: Path to write the JSON file

    Returns:
        dict with the images.json structure
    """
    output_path = Path(output_path)
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

        # Issue #139: an image written to its own file must always keep its
        # entry — otherwise two files can exist on disk with one manifest row.
        if content_hash is not None and not img.written_rel_path:
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)

        position = _get_position(img)
        image_entry: dict[str, object] = {
            "paragraph_index": position,
            "mime_type": img.mime_type,
        }

        # Issue #139: carry the exact relative path the markdown uses for
        # this image (set by MarkdownGenerator when the file was written to
        # the {stem}_images/ directory). Downstream can correlate manifest
        # entries with the md references instead of concluding "no images".
        if img.written_rel_path:
            image_entry["file_path"] = img.written_rel_path

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
        elif img.temp_path is not None and img.temp_path.exists():
            with open(img.temp_path, "rb") as f:
                image_entry["data_base64"] = base64.b64encode(f.read()).decode("ascii")

        images_list.append(image_entry)

    # Issue #139: the extraction collection and the files written to
    # {stem}_images/ can diverge (e.g. a separate-images step wrote the files
    # from another result). Never emit an empty manifest while the markdown
    # references images — rebuild the entries from those references instead.
    if not images_list:
        recovered = _entries_from_markdown(output_path)
        if recovered:
            logger.warning(
                "images.json manifest %s would have been EMPTY while the markdown "
                "references %d image file(s) — rebuilt the manifest from %s "
                "(issue #139)",
                output_path,
                len(recovered),
                _sibling_images_dir(output_path),
            )
            images_list = recovered

    output = {"images": images_list, "total": len(images_list)}

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # Issue #139: an empty manifest with non-empty {stem}_images/ must never
    # be silent — downstream strips image refs when the manifest is empty.
    if not images_list:
        _warn_on_empty_manifest(output_path)

    return output
