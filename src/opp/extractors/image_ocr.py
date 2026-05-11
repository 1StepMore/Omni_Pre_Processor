from pathlib import Path
from typing import List

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import ExtractionResult


class ImageOCRExtractor(ExtractorBase):

    def supported_extensions(self) -> List[str]:
        return [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

    def extract(self, input_path: Path) -> ExtractionResult:
        raise NotImplementedError("Image OCR extraction not yet implemented")