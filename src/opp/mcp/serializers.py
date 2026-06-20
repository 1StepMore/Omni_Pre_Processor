"""Serialization utilities for OPP MCP interface."""

import base64
from pathlib import Path
from typing import Any

from opp.pipeline import ProcessingResult
from opp.utils.dataclasses import (
    AttachmentData,
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
    TextBlockData,
    SlideData,
)


def _serialize_paragraph(paragraph: ParagraphData) -> dict[str, Any]:
    return {
        "text": paragraph.text,
        "style": paragraph.style,
        "level": paragraph.level,
        "chapter": paragraph.chapter,
        "page": paragraph.page,
    }


def _serialize_table(table: TableData) -> dict[str, Any]:
    return {
        "headers": table.headers,
        "rows": table.rows,
    }


def _serialize_image(
    image: ImageData,
    include_base64: bool = True,
    resource_dir: Path | None = None,
) -> dict[str, Any]:
    img_dict: dict[str, Any] = {
        "mime_type": image.mime_type,
        "width": image.width,
        "height": image.height,
        "paragraph_index": image.paragraph_index,
        "page_number": image.page_number,
        "slide_index": image.slide_index,
        "element_index": image.element_index,
        "spine_index": image.spine_index,
    }
    if include_base64 and image.data:
        img_dict["data_base64"] = base64.b64encode(image.data).decode("utf-8")
    return img_dict


def _serialize_attachment(
    attachment: AttachmentData,
    include_base64: bool = True,
) -> dict[str, Any]:
    att_dict: dict[str, Any] = {
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
    }
    if include_base64 and attachment.data:
        att_dict["data"] = base64.b64encode(attachment.data).decode("utf-8")
    return att_dict


def _serialize_slide(slide: SlideData) -> dict[str, Any]:
    return {
        "index": slide.index,
        "shapes": [_serialize_paragraph(p) for p in slide.shapes],
        "notes": slide.notes,
    }


def _serialize_text_block(block: TextBlockData) -> dict[str, Any]:
    return {
        "text": block.text,
        "bbox": block.bbox,
        "page": block.page,
    }


def _serialize_metadata(metadata: DocumentMetadata | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        "page_count": metadata.page_count,
        "file_size": metadata.file_size,
        "format_type": metadata.format_type,
        "subject": metadata.subject,
        "sender": metadata.sender,
        "to": metadata.to,
        "cc": metadata.cc,
        "date": metadata.date,
    }


def _serialize_extraction_result(
    result: ExtractionResult | None,
    include_base64: bool = True,
    resource_dir: Path | None = None,
) -> dict[str, Any] | None:
    if result is None:
        return None

    return {
        "paragraphs": [_serialize_paragraph(p) for p in result.paragraphs],
        "tables": [_serialize_table(t) for t in result.tables],
        "images": [
            _serialize_image(img, include_base64, resource_dir)
            for img in result.images
        ],
        "attachments": [
            _serialize_attachment(att, include_base64)
            for att in result.attachments
        ],
        "metadata": _serialize_metadata(result.metadata),
        "warnings": result.warnings or [],
        "is_transcription": result.is_transcription,
    }


class ExtractionResultSerializer:
    def serialize(
        self,
        result: ProcessingResult | None,
        include_base64: bool = True,
        resource_dir: Path | None = None,
    ) -> dict[str, Any]:
        if result is None:
            return {
                "success": False,
                "error": "No result provided",
            }

        try:
            format_type_str = (
                result.format_type.value
                if hasattr(result.format_type, "value")
                else str(result.format_type)
            )

            data = {
                "content": result.content,
                "format_type": format_type_str,
                "images_stored": result.images_stored,
                "duration_ms": result.duration_ms,
                "errors": result.errors or [],
                "warnings": result.warnings or [],
                "extraction_result": _serialize_extraction_result(
                    result.extraction_result, include_base64, resource_dir
                ),
            }

            return {
                "success": True,
                **data,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def serialize_batch(
        self,
        results: list[ProcessingResult],
        include_base64: bool = True,
        resource_dir: Path | None = None,
    ) -> list[dict[str, Any]]:
        return [
            self.serialize(r, include_base64, resource_dir)
            for r in results
        ]