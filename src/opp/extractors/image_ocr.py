from pathlib import Path
from typing import List

from PIL import Image

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError
from opp.logger import logger


TESSERACT_INSTALL_GUIDE = (
    "Tesseract OCR is not installed. "
    "On Ubuntu/Debian: sudo apt install tesseract-ocr. "
    "On macOS: brew install tesseract. "
    "On Windows: download installer from https://github.com/UB-Mannheim/tesseract/wiki"
)

RAPIDOCR_INSTALL_GUIDE = (
    "RapidOCR is not installed. "
    "Install with: pip install rapidocr-onnxruntime"
)


class ImageOCRExtractor(ExtractorBase):

    def supported_extensions(self) -> List[str]:
        return [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

    def extract(self, input_path: Path) -> ExtractionResult:
        import os
        self.validate_file(input_path)

        engine = os.environ.get("OPP_OCR_ENGINE", "tesseract")
        lang = os.environ.get("OPP_OCR_LANG", "eng")

        if engine == "rapidocr":
            result = self._extract_rapidocr(input_path)
        else:
            result = self._extract_tesseract(input_path, lang)

            if result.get("error") == "OCR_NOT_INSTALLED":
                result = self._extract_rapidocr(input_path)

        if result.get("error") in ("OCR_NOT_INSTALLED", "RAPIDOCR_NOT_INSTALLED"):
            error_warnings = [result.get("install_guide", "No OCR engine available")]
            return ExtractionResult(
                paragraphs=[ParagraphData(text="", level=0, style="Normal")],
                tables=[],
                images=[],
                metadata=DocumentMetadata(
                    file_size=input_path.stat().st_size,
                    format_type="IMAGE"
                ),
                warnings=error_warnings,
            )

        paragraphs = [ParagraphData(text=result["text"], level=0, style="Normal")]
        result_warnings = []
        if result.get("warning"):
            result_warnings.append(result["warning"])

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=DocumentMetadata(
                file_size=input_path.stat().st_size,
                format_type="IMAGE"
            ),
            warnings=result_warnings,
        )

    def _extract_tesseract(self, image_path: Path, lang: str = "eng") -> dict:
        try:
            img = Image.open(image_path)
        except Exception as e:
            logger.warning(f"Cannot open image for OCR: {e}")
            raise CorruptedFileError(f"Cannot open image: {image_path}")

        try:
            import pytesseract
        except ImportError:
            return {
                "text": "",
                "confidence": 0.0,
                "language": lang,
                "error": "OCR_NOT_INSTALLED",
                "install_guide": TESSERACT_INSTALL_GUIDE,
            }

        if img.mode not in ("RGB", "L", "RGBA"):
            img = img.convert("RGB")

        dpi = img.info.get("dpi", (72, 72))
        dpi_warning = None
        if isinstance(dpi, tuple) and len(dpi) >= 2:
            dpi_x = dpi[0] if dpi[0] else 72
            if dpi_x < 72:
                dpi_warning = f"Low resolution image ({dpi_x} DPI). OCR accuracy may be reduced."

        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["tesseract", "not found", "could not find", "not installed"]):
                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": lang,
                    "error": "OCR_NOT_INSTALLED",
                    "install_guide": TESSERACT_INSTALL_GUIDE,
                }
            raise CorruptedFileError(f"OCR extraction failed: {e}")

        result = {
            "text": text,
            "confidence": 0.0,
            "language": lang,
        }
        if dpi_warning:
            result["warning"] = dpi_warning

        return result

    def _extract_rapidocr(self, image_path: Path) -> dict:
        try:
            from rapidocr_onnxruntime import RapidOCRSentenceExtractor
        except ImportError:
            return {
                "text": "",
                "confidence": 0.0,
                "language": "eng",
                "error": "RAPIDOCR_NOT_INSTALLED",
                "install_guide": RAPIDOCR_INSTALL_GUIDE,
            }

        try:
            engine = RapidOCRSentenceExtractor()
            ocr_result = engine(str(image_path))
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["rapidocr", "onnx", "runtime"]):
                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": "eng",
                    "error": "RAPIDOCR_NOT_INSTALLED",
                    "install_guide": RAPIDOCR_INSTALL_GUIDE,
                }
            raise CorruptedFileError(f"RapidOCR extraction failed: {e}")

        if ocr_result is None or len(ocr_result) == 0:
            return {
                "text": "",
                "confidence": 0.0,
                "language": "eng",
            }

        text_parts = []
        total_confidence = 0.0
        for item in ocr_result:
            if len(item) >= 2:
                text_parts.append(item[1])
                total_confidence += item[2] if len(item) > 2 else 0.0

        avg_confidence = total_confidence / len(ocr_result) if ocr_result else 0.0

        return {
            "text": "\n".join(text_parts),
            "confidence": avg_confidence,
            "language": "eng",
        }