from dataclasses import replace
from pathlib import Path
import re
from typing import Any

import fitz

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
    TextBlockData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError
from opp.logger import logger


class PDFExtractor(ExtractorBase):
    CHINESE_NUMERALS = "一二三四五六七八九十百千万零两"

    # Issue OPP #5: when text-layer extraction returns fewer than this
    # many characters on a page, assume the page is image-only / scanned
    # and run OCR on the full page as a fallback. Threshold chosen
    # empirically: a page with only title metadata (e.g. "Technical
    # Report", 16 chars) triggers OCR; a normal text-layer page with
    # body content (100+ chars) does not.
    OCR_FALLBACK_TEXT_THRESHOLD = 30

    # Level 1 patterns
    _LEVEL1_PATTERNS = [
        re.compile(r"^[{}]+、".format(CHINESE_NUMERALS)),  # 一、二、三、
        re.compile(r"^第[{}{}\d]+章".format(CHINESE_NUMERALS, "\\d")),  # 第一章, 第1章
        re.compile(r"^\d+\.$"),  # 1. 2. 3.
    ]
    # Level 2 patterns
    _LEVEL2_PATTERNS = [
        re.compile(r"^第[{}{}\d]+节".format(CHINESE_NUMERALS, "\\d")),  # 第一节
        re.compile(r"^\d+\.\d+$"),  # 1.1 2.1
    ]

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def _detect_heading_level(self, text: str) -> int | None:
        """Detect if text is a Chinese heading and return its level."""
        if not text:
            return None
        for pattern in self._LEVEL1_PATTERNS:
            if pattern.match(text):
                return 1
        for pattern in self._LEVEL2_PATTERNS:
            if pattern.match(text):
                return 2
        return None

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            doc: fitz.Document = fitz.open(input_path)
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise PasswordProtectedError(f"文件受密码保护: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        try:
            if doc.page_count == 0:
                warnings.append("PDF为空")
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

            paragraphs = []
            for b in text_blocks:
                level = self._detect_heading_level(b.text)
                if level:
                    paragraphs.append(ParagraphData(text=b.text, style=f"Heading {level}", level=level, page=b.page))
                else:
                    paragraphs.append(ParagraphData(text=b.text, style=None, level=None, page=b.page))

            # Merge TOC entries with body paragraphs (dedupe by text+level)
            toc_paragraphs = self._extract_toc_from_doc(doc)
            existing_texts = {(p.text.strip(), p.level) for p in toc_paragraphs}
            merged = toc_paragraphs.copy()
            for p in paragraphs:
                if (p.text.strip(), p.level) not in existing_texts:
                    merged.append(p)
            paragraphs = merged

            # Build chapter-paragraph map based on page numbers
            paragraphs = self._build_chapter_paragraph_map(toc_paragraphs, paragraphs)

            metadata = replace(metadata, page_count=doc.page_count)
        finally:
            doc.close()

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def _init_rapidocr(self):
        """Initialize RapidOCR engine once for reuse."""
        try:
            from rapidocr_onnxruntime import RapidOCRSentenceExtractor
            return RapidOCRSentenceExtractor()
        except ImportError:
            logger.warning("_init_rapidocr: rapidocr_onnxruntime not installed, OCR fallback unavailable")
            return None

    def _ocr_tesseract(self, img: Any, lang: str) -> str | None:
        try:
            import pytesseract
        except ImportError:
            return self._ocr_rapidocr(img, None)

        try:
            if img.mode not in ("RGB", "L", "RGBA"):
                img = img.convert("RGB")
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text else None
        except Exception as e:
            logger.debug(f"Tesseract OCR failed, falling back to RapidOCR: {e}")
            return self._ocr_rapidocr(img, None)

    def _ocr_rapidocr(self, img: Any, engine: Any) -> str | None:
        if engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCRSentenceExtractor
                engine = RapidOCRSentenceExtractor()
            except ImportError:
                logger.warning("_ocr_rapidocr: rapidocr_onnxruntime not installed, OCR fallback unavailable")
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
                    if not text_parts:
                        logger.debug("_ocr_rapidocr: RapidOCR returned no text parts")
                        return None
                    return "\n".join(text_parts)
                logger.debug("_ocr_rapidocr: RapidOCR returned no result")
                return None
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"_ocr_rapidocr: RapidOCR extraction failed: {e}")
            return None

    def extract_text_blocks(self, doc: fitz.Document) -> list[TextBlockData]:
        result: list[TextBlockData] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("blocks")
            page_text_chars = 0
            page_blocks: list[TextBlockData] = []
            for block in blocks:
                if len(block) < 6:
                    continue
                x0, y0, x1, y1, text, *_ = block
                text = text.strip()
                if not text:
                    continue
                page_text_chars += len(text)
                page_blocks.append(TextBlockData(
                    text=text,
                    bbox=(x0, y0, x1, y1),
                    page=page_num + 1,
                ))

            # OCR fallback for image-only / scanned pages (Issue OPP #5):
            # if text-layer extraction returned very little text, the page
            # is likely a scanned/image-only PDF with no embedded text.
            # Render the page as a high-DPI image and run Tesseract /
            # RapidOCR on it via the existing _ocr_tesseract /
            # _ocr_rapidocr helpers (same infrastructure as the image
            # extraction path, no new deps).
            if page_text_chars < self.OCR_FALLBACK_TEXT_THRESHOLD:
                ocr_blocks = self._ocr_page(page, page_num)
                if ocr_blocks:
                    result.extend(ocr_blocks)
                    continue
                # OCR unavailable or found no text — fall through to
                # whatever text-layer content we got (likely just title
                # metadata). The page will still emit any extracted
                # blocks, no silent data loss.
            result.extend(page_blocks)
        return result

    def _ocr_page(self, page: fitz.Page, page_num: int) -> list[TextBlockData]:
        """OCR a single page as a fallback for image-only / scanned PDFs.

        Renders the page as a 200-DPI image and runs the existing
        Tesseract / RapidOCR helpers (same infra as the image
        extraction path in `extract_images`). Returns TextBlockData
        for the full page bbox, or empty list if OCR is unavailable
        or finds no text.

        Silent no-op when neither Tesseract nor RapidOCR is installed
        — the text-layer path still runs and the page emits whatever
        metadata it could extract.
        """
        try:
            pix = page.get_pixmap(dpi=200)
        except Exception as e:
            logger.debug(f"page.get_pixmap failed for page {page_num}: {e}")
            return []

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(pix.tobytes("png")))
        except ImportError:
            logger.debug("PIL not available for full-page OCR fallback")
            return []
        except Exception as e:
            logger.debug(f"Failed to convert page pixmap to PIL Image: {e}")
            return []

        text = self._ocr_tesseract(img, lang="eng")
        if not text:
            return []

        return [TextBlockData(
            text=text,
            bbox=(0, 0, pix.width, pix.height),
            page=page_num + 1,
        )]

    def detect_tables(self, doc: fitz.Document) -> list:
        result: list[TableData] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            table_page = page.find_tables()
            if table_page is None:
                continue
            for table in table_page:
                extracted = table.extract()
                if extracted and len(extracted) > 1:
                    headers = table.header.names if table.header else []
                    rows = extracted[1:]
                    result.append(TableData(headers=headers, rows=rows))
        return result

    def extract_images(self, doc: fitz.Document) -> list[ImageData]:
        result: list[ImageData] = []
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
                        page_number=page_num + 1,
                    ))
                except Exception as e:
                    logger.debug(f"Image extraction failed: {e}")
                    continue
        return result

    def _extract_toc_from_doc(self, doc: fitz.Document) -> list[ParagraphData]:
        """Extract TOC from already-open PDF document."""
        toc_entries = doc.get_toc()
        if not toc_entries:
            return []
        return [
            ParagraphData(
                text=toc_entry[1],
                style=f"Heading {toc_entry[0]}",
                level=toc_entry[0],
                page=toc_entry[2] if len(toc_entry) > 2 else None,
            )
            for toc_entry in toc_entries
        ]

    def _build_chapter_paragraph_map(self, toc_entries: list[ParagraphData], paragraphs: list[ParagraphData]) -> list[ParagraphData]:
        """Map each paragraph to a chapter based on page number from TOC entries.
        
        TOC entries from fitz doc.get_toc() return [level, title, page, ...] where page is index 2.
        This method sorts TOC entries by page number and assigns chapters to paragraphs.
        """
        # Filter TOC entries that have page info and are level 1 (chapters)
        chapter_entries = [t for t in toc_entries if t.page is not None and t.level == 1]
        if not chapter_entries:
            return paragraphs
        
        # Sort by page number
        chapter_entries.sort(key=lambda x: x.page)
        
        result = []
        for p in paragraphs:
            if p.page is None:
                # Paragraph without page info gets None chapter
                result.append(replace(p, chapter=None))
            else:
                # Find the chapter this paragraph belongs to
                chapter = None
                for i, ch in enumerate(chapter_entries):
                    if p.page < ch.page:
                        # Paragraph is before this chapter
                        break
                    chapter = ch.text
                result.append(replace(p, chapter=chapter))
        
        return result

    def extract_toc(self, input_path: Path) -> list[ParagraphData]:
        try:
            doc: fitz.Document = fitz.open(input_path)
        except Exception as e:
            logger.debug(f"Failed to open PDF for TOC extraction: {e}")
            return []

        toc_entries = doc.get_toc()
        doc.close()

        if not toc_entries:
            return []

        return [
            ParagraphData(
                text=toc_entry[1],
                style=f"Heading {toc_entry[0]}",
                level=toc_entry[0],
                page=toc_entry[2] if len(toc_entry) > 2 else None,
            )
            for toc_entry in toc_entries
        ]
