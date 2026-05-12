from dataclasses import replace
from pathlib import Path
from typing import List, Optional
import os

import fitz

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
    TextBlockData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError
from opp.logger import logger


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

        # Pure image/scan PDF: automatic OCR fallback
        # Trigger OCR when no text blocks found (regardless of embedded images)
        if not text_blocks:
            ocr_engine = os.environ.get("OPP_OCR_ENGINE", "tesseract")
            ocr_lang = os.environ.get("OPP_OCR_LANG", "eng")
            logger.info(f"PDF无文字，触发OCR: 引擎={ocr_engine}, 语言={ocr_lang}, 共{doc.page_count}页")
            warnings.append(f"PDF为扫描件，使用{ocr_engine}引擎+{ocr_lang}语言进行OCR...")
            ocr_result = self._extract_via_ocr(doc)
            if ocr_result:
                paragraphs = ocr_result
                total_chars = sum(len(p.text) for p in ocr_result)
                logger.info(f"OCR成功: {len(ocr_result)}段落, {total_chars}字符")
                warnings.append(f"OCR提取成功，共{len(ocr_result)}段落")
            else:
                logger.warning("OCR未能提取到文字")
                warnings.append("PDF为扫描件，OCR未能提取文本")

        metadata = replace(metadata, page_count=doc.page_count)
        doc.close()

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def _extract_via_ocr(self, doc: fitz.Document) -> Optional[List[ParagraphData]]:
        """Extract text from PDF via OCR when no text is available.

        This handles pure image/scan PDFs by rendering each page and running OCR.

        Args:
            doc: The PyMuPDF document

        Returns:
            List of ParagraphData if OCR succeeded, None if OCR failed
        """
        from PIL import Image
        from io import BytesIO

        all_paragraphs: List[ParagraphData] = []
        ocr_engine = os.environ.get("OPP_OCR_ENGINE", "tesseract")
        ocr_lang = os.environ.get("OPP_OCR_LANG", "eng")

        rapidocr_engine = None
        if ocr_engine == "rapidocr":
            rapidocr_engine = self._init_rapidocr()

        for page_num in range(doc.page_count):
            page = doc[page_num]
            try:
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                img_data = pix.tobytes("png")
                img = Image.open(BytesIO(img_data))

                if ocr_engine == "rapidocr" and rapidocr_engine:
                    text = self._ocr_rapidocr(img, rapidocr_engine)
                else:
                    text = self._ocr_tesseract(img, ocr_lang)

                if text:
                    all_paragraphs.append(ParagraphData(
                        text=text,
                        style=None,
                        level=None
                    ))
            except Exception:
                continue

        return all_paragraphs if all_paragraphs else None

    def _init_rapidocr(self):
        """Initialize RapidOCR engine once for reuse."""
        try:
            from rapidocr_onnxruntime import RapidOCRSentenceExtractor
            return RapidOCRSentenceExtractor()
        except ImportError:
            return None

    def _ocr_tesseract(self, img, lang: str) -> Optional[str]:
        try:
            import pytesseract
        except ImportError:
            return self._ocr_rapidocr(img, None)

        try:
            if img.mode not in ("RGB", "L", "RGBA"):
                img = img.convert("RGB")
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text else None
        except Exception:
            return self._ocr_rapidocr(img, None)

    def _ocr_rapidocr(self, img, engine) -> Optional[str]:
        if engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCRSentenceExtractor
                engine = RapidOCRSentenceExtractor()
            except ImportError:
                return None

        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name)
                tmp_path = tmp.name

            try:
                result = engine(tmp_path)
                if result:
                    text_parts = []
                    for item in result:
                        if len(item) >= 2:
                            text_parts.append(item[1])
                    return "\n".join(text_parts) if text_parts else None
                return None
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            return None

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
        result: List[TableData] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            table_page = page.find_tables()
            if table_page is None:
                continue
            for table in table_page:
                extracted = table.extract()
                if extracted:
                    headers = table.header.names if table.header else []
                    rows = extracted
                    result.append(TableData(headers=headers, rows=rows))
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
