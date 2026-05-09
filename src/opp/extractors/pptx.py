from dataclasses import replace
from pathlib import Path
from typing import List

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    SlideData,
)
from opp.utils.exceptions import CorruptedFileError, UnsupportedFormatError


class PPTXExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".pptx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            prs = Presentation(input_path)
        except Exception as e:
            if ".pptm" in str(input_path).lower():
                raise UnsupportedFormatError(f"不支持的PPTX格式（宏已启用）: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        slides = self.extract_slides(prs)
        images = self.extract_images(prs)

        all_paragraphs: List[ParagraphData] = []
        for slide_data in slides:
            all_paragraphs.extend(slide_data.shapes)

        if not all_paragraphs:
            warnings.append("演示文稿为空")

        metadata = replace(metadata, page_count=len(prs.slides))

        return ExtractionResult(
            paragraphs=all_paragraphs,
            tables=[],
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def extract_slides(self, prs: Presentation) -> List[SlideData]:
        result: List[SlideData] = []
        for i, slide in enumerate(prs.slides):
            shapes = self.extract_shapes(slide)
            notes = self.extract_notes(slide)
            result.append(SlideData(
                index=i,
                shapes=shapes,
                notes=notes,
            ))
        return result

    def extract_shapes(self, slide) -> List[ParagraphData]:
        result: List[ParagraphData] = []
        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                result.extend(self._flatten_group(shape))
            elif shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    result.append(ParagraphData(
                        text=text,
                        style=shape.shape_type.name if hasattr(shape.shape_type, 'name') else None,
                        level=None,
                    ))
        return result

    def _flatten_group(self, group) -> List[ParagraphData]:
        result: List[ParagraphData] = []
        for shape in group.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    result.append(ParagraphData(
                        text=text,
                        style=shape.shape_type.name if hasattr(shape.shape_type, 'name') else None,
                        level=None,
                    ))
        return result

    def extract_notes(self, slide) -> str:
        notes_slide = slide.notes_slide
        if notes_slide and notes_slide.notes_text_frame:
            return notes_slide.notes_text_frame.text.strip()
        return ""

    def extract_images(self, prs: Presentation) -> List[ImageData]:
        result: List[ImageData] = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "image"):
                    try:
                        image = shape.image
                        result.append(ImageData(
                            data=image.blob,
                            mime_type=image.content_type,
                            width=image.size.width if hasattr(image.size, 'width') else None,
                            height=image.size.height if hasattr(image.size, 'height') else None,
                        ))
                    except Exception:
                        continue
        return result
