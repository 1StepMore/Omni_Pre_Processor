"""Pydantic schemas for manifest.json — the extraction manifest crossing from OPP to ORF (and consumed by OL).

Every OPP extraction run produces a manifest.json that records source-file
metadata, extraction outputs (MD / XLIFF paths and statistics), image summaries,
resource references, and skeleton.zip information.  Downstream tools use this
manifest to discover the artefacts produced by OPP.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Metadata about the original source document that OPP processed."""

    file_path: str = Field(
        ...,
        description="Absolute path to the source file on the machine where OPP ran.",
    )
    original_filename: str = Field(
        ...,
        description="Original filename (basename) of the source document.",
    )
    format: str = Field(
        ...,
        description="Detected file format (e.g. 'DOCX', 'PDF', 'PPTX').",
        examples=["DOCX", "PDF", "PPTX"],
    )
    file_size_bytes: int = Field(
        ...,
        ge=0,
        description="Size of the source file in bytes.",
    )
    file_hash_md5: str = Field(
        ...,
        description="MD5 hex digest of the source file for deduplication and integrity checks.",
        min_length=32,
        max_length=32,
    )

    model_config = {"extra": "ignore"}


class OutputEntry(BaseModel):
    """Statistics and path for a single extraction output (markdown or xliff)."""

    path: Optional[str] = Field(
        default=None,
        description="Relative or absolute path to the output file (None if this output was not produced).",
    )
    paragraph_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of paragraphs extracted (markdown only).",
    )
    table_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of tables extracted (markdown only).",
    )
    trans_unit_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of <trans-unit> elements in the XLIFF output (xliff only).",
    )

    model_config = {"extra": "ignore"}


class ImagesJsonOutput(BaseModel):
    """Reference to the generated images.json sidecar file."""

    path: str = Field(
        ...,
        description="Path to the images.json file that carries per-image metadata for ORF.",
    )

    model_config = {"extra": "ignore"}


class ExtractionOutputs(BaseModel):
    """Container for all extraction output references and statistics."""

    markdown: Optional[OutputEntry] = Field(
        default=None,
        description="Markdown output metadata (set when OPP runs with markdown target).",
    )
    xliff: Optional[OutputEntry] = Field(
        default=None,
        description="XLIFF output metadata (set when OPP runs with xliff target).",
    )
    images_json: Optional[ImagesJsonOutput] = Field(
        default=None,
        description="images.json sidecar output metadata.",
    )

    model_config = {"extra": "ignore"}


class ImageSummary(BaseModel):
    """Lightweight per-image summary carried inside manifest.json.

    This is NOT the same as the full ImageEntry in images.json — the manifest
    only stores MIME type, dimensions, and byte count for quick aggregation.
    """

    mime_type: str = Field(
        ...,
        description="MIME type of the image (e.g. 'image/png').",
    )
    width: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image width in pixels (may be unknown).",
    )
    height: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image height in pixels (may be unknown).",
    )
    data_size_bytes: int = Field(
        ...,
        ge=0,
        description="Size of the image data in bytes (0 for empty or unavailable data).",
    )

    model_config = {"extra": "ignore"}


class ExtractionSection(BaseModel):
    """The 'extraction' block inside manifest.json — summary of what OPP produced."""

    source_lang: str = Field(
        ...,
        description="ISO 639-1 source language code (e.g. 'zh', 'en').",
        min_length=2,
        max_length=5,
    )
    target_lang: str = Field(
        ...,
        description="ISO 639-1 target language code (e.g. 'en', 'fr').",
        min_length=2,
        max_length=5,
    )
    outputs: ExtractionOutputs = Field(
        default_factory=ExtractionOutputs,
        description="Paths and statistics for each output artefact.",
    )
    images: list[ImageSummary] = Field(
        default_factory=list,
        description="Per-image summary (MIME type, dimensions, byte size) for quick inspection.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings emitted during extraction.",
    )

    model_config = {"extra": "ignore"}


class ResourcesInfo(BaseModel):
    """Reference to the resource-storage directory managed by OPP."""

    storage_dir: str = Field(
        ...,
        description="Absolute path to the resource storage directory.",
    )
    image_count: int = Field(
        ...,
        ge=0,
        description="Number of image files stored in the resource directory.",
    )

    model_config = {"extra": "ignore"}


class SkeletonInfo(BaseModel):
    """Metadata about the preserved skeleton.zip for DOCX/PPTX back-fill."""

    path: str = Field(
        ...,
        description="Path to the skeleton.zip file that preserves the original OOXML ZIP structure.",
    )
    format: str = Field(
        ...,
        description="Archive format (always 'ZIP' for OOXML skeletons).",
    )
    key_files: list[str] = Field(
        default_factory=list,
        description="List of key file paths preserved inside skeleton.zip (e.g. 'word/document.xml').",
    )

    model_config = {"extra": "ignore"}


class Manifest(BaseModel):
    """Top-level model for manifest.json — the extraction manifest.

    This is the primary contract between OPP and downstream tools (OL, ORF).
    Every OPP extraction run produces exactly one manifest.json that conforms
    to this schema.
    """

    manifest_version: str = Field(
        ...,
        description="Semantic version of the manifest format (currently '1.0').",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="UUID for end-to-end tracing across OPP -> OL -> ORF (B2).",
    )
    generated_at: str = Field(
        ...,
        description="ISO 8601 timestamp when the manifest was generated.",
    )
    tool: str = Field(
        ...,
        description="Name of the tool that produced this manifest (always 'OPP').",
    )
    tool_version: str = Field(
        ...,
        description="Version of OPP that produced this manifest.",
    )
    source: SourceInfo = Field(
        ...,
        description="Metadata about the original source document.",
    )
    extraction: ExtractionSection = Field(
        ...,
        description="Summary of extraction outputs, images, and warnings.",
    )
    resources: ResourcesInfo = Field(
        ...,
        description="Reference to the resource-storage directory.",
    )
    skeleton: Optional[SkeletonInfo] = Field(
        default=None,
        description="Skeleton.zip metadata (only present for OOXML source formats).",
    )

    model_config = {"extra": "ignore"}
