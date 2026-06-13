"""Pydantic schemas for images.json — the image manifest crossing from OPP to ORF.

The images.json file carries per-image metadata (position, MIME type, dimensions,
and optionally base64-encoded pixel data) so that downstream ORF tools can
reinject images at the correct document positions without re-extracting them.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ImageEntry(BaseModel):
    """A single image entry in images.json.

    Describes one extracted image from a source document, including its
    document position, MIME type, dimensions, and optionally raw pixel data
    as base64.  Floating images carry additional anchor-coordinate fields.
    """

    file_path: Optional[str] = Field(
        default=None,
        description="Filesystem path to the image file (set when images are stored on disk rather than embedded as base64).",
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the image (e.g. 'image/png', 'image/jpeg').",
        examples=["image/png", "image/jpeg"],
    )
    width: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image width in pixels (may be unknown for some source formats).",
    )
    height: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image height in pixels (may be unknown for some source formats).",
    )
    data_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Size of the image data in bytes (set in manifest.json; optional in images.json).",
    )
    data_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded image bytes when images are embedded inline.",
    )

    # Document position — consumers use this to place the image at the right
    # location during back-fill.  Only ONE of these position fields is
    # meaningful per source format (DOCX → paragraph_index, PDF → page_number,
    # PPTX → slide_index, etc.).
    paragraph_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based paragraph index for DOCX inline drawings (None for floating images).",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-based page number for PDF images.",
    )
    slide_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based slide index for PPTX images.",
    )
    element_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based DOM element index for HTML images.",
    )
    spine_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-based spine-order index for EPUB images.",
    )

    # Floating-image metadata (DOCX anchor drawings only).
    # When is_floating is True, wp_anchor_h/wp_anchor_v carry the original
    # wp:positionH/wp:positionV offsets in EMU (English Metric Units;
    # 914400 EMU = 1 inch).  ORF reads these to reconstruct <wp:anchor>
    # blocks during DOCX back-fill.
    is_floating: Optional[bool] = Field(
        default=None,
        description="True if the image is a floating (wp:anchor) drawing.  None/absent for inline images.",
    )
    wp_anchor_h: Optional[int] = Field(
        default=None,
        description="Horizontal anchor offset in EMU units (only meaningful when is_floating is True).",
    )
    wp_anchor_v: Optional[int] = Field(
        default=None,
        description="Vertical anchor offset in EMU units (only meaningful when is_floating is True).",
    )

    model_config = {"extra": "ignore"}


class ImageManifest(BaseModel):
    """Top-level container for images.json.

    Wraps the list of ImageEntry objects that represent every image
    extracted from a source document.
    """

    images: list[ImageEntry] = Field(
        default_factory=list,
        description="Ordered list of extracted images with position and metadata.",
    )

    model_config = {"extra": "ignore"}
