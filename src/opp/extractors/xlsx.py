from datetime import datetime, date
from pathlib import Path
from typing import List

import openpyxl

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import ValidationError


class XLSXExtractor(ExtractorBase):
    MAX_ROWS_WARNING = 10000

    def supported_extensions(self) -> List[str]:
        return [".xlsx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            wb = openpyxl.load_workbook(input_path, data_only=True)
        except Exception as e:
            if "password" in str(e).lower():
                raise ValidationError(f"文件受密码保护: {input_path}")
            raise ValueError(f"无法打开XLSX文件: {input_path}")

        paragraphs: List[ParagraphData] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            paragraphs.append(ParagraphData(
                text=f"=== Sheet: {sheet_name} ===",
                style="sheet_header",
            ))

            if ws.max_row > self.MAX_ROWS_WARNING:
                warnings.append(f"工作表 '{sheet_name}' 超过 {self.MAX_ROWS_WARNING} 行，已截断")

            max_col = ws.max_column or 1
            for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row, self.MAX_ROWS_WARNING), max_col=max_col), start=1):
                row_values = []
                for cell in row:
                    val = cell.value
                    if val is None:
                        row_values.append("")
                    elif isinstance(val, (datetime, date)):
                        row_values.append(val.isoformat())
                    else:
                        row_values.append(str(val))
                line = " | ".join(row_values).strip()
                if line:
                    paragraphs.append(ParagraphData(
                        text=line,
                        style=None,
                    ))

        if not paragraphs:
            warnings.append("工作簿为空")

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=metadata,
            warnings=warnings,
        )