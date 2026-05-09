from dataclasses import replace
from pathlib import Path
from typing import List

import fitz

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TextBlockData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class PDFExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            doc: fitz.Document = fitz.open(input_path)
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise PasswordProtectedError(f"文件受密码保护: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        if doc.page_count == 0:
            warnings.append("PDF为空")
            doc.close()
            metadata = replace(metadata, page_count=0)
            return ExtractionResult(
                paragraphs=[],
                tables=[],
                images=[],
                metadata=metadata,
                warnings=warnings,
            )

        text_blocks = self.extract_text_blocks(doc)
        tables = self.detect_tables(doc)
        images = self.extract_images(doc)

        paragraphs = [
            ParagraphData(text=b.text, style=None, level=None)
            for b in text_blocks
        ]

        if not text_blocks and not images:
            warnings.append("PDF为扫描件，无可提取文本")

        metadata = replace(metadata, page_count=doc.page_count)
        doc.close()

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def extract_text_blocks(self, doc: fitz.Document) -> List[TextBlockData]:
        result: List[TextBlockData] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("blocks")
            for block in blocks:
                if len(block) < 6:
                    continue
                x0, y0, x1, y1, text, *_ = block
                text = text.strip()
                if not text:
                    continue
                result.append(TextBlockData(
                    text=text,
                    bbox=(x0, y0, x1, y1),
                    page=page_num + 1,
                ))
        return result

    def detect_tables(self, doc: fitz.Document) -> List:
        result: List = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            tables = page.find_tables()
            if tables:
                for table in tables:
                    result.append(table)
        return result

    def extract_images(self, doc: fitz.Document) -> List[ImageData]:
        result: List[ImageData] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_info in image_list:
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    mime_type = f"image/{image_ext}"
                    result.append(ImageData(
                        data=image_bytes,
                        mime_type=mime_type,
                    ))
                except Exception:
                    continue
        return result
