from pathlib import Path
from typing import List

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import ExtractionResult


class EmailExtractor(ExtractorBase):

    def supported_extensions(self) -> List[str]:
        return [".eml", ".msg"]

    def extract(self, input_path: Path) -> ExtractionResult:
        raise NotImplementedError("Email extraction not yet implemented")