from pathlib import Path
from typing import List

import chardet
import pandas as pd

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
)


class CSVExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".csv"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        df = self._read_csv_with_encoding(input_path)

        # Warn about large files
        row_count = len(df)
        if row_count > 10000:
            warnings.append(f"文件行数较多 ({row_count} 行)，可能影响处理性能")

        headers = df.columns.tolist()

        # Pad inconsistent columns
        max_cols = df.shape[1]
        padded_rows = []
        for _, row in df.iterrows():
            padded_row = list(row.values)
            while len(padded_row) < max_cols:
                padded_row.append("")
            padded_rows.append(padded_row)

        paragraphs = []
        for idx, row in enumerate(padded_rows):
            row_text = "\t".join(str(val) for val in row)
            paragraphs.append(ParagraphData(text=row_text))

        tables = [
            TableData(
                headers=[str(h) for h in headers],
                rows=padded_rows,
            )
        ]

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=[],
            metadata=metadata,
            warnings=warnings,
        )

    def _read_csv_with_encoding(self, input_path: Path) -> pd.DataFrame:
        # Try UTF-8 first
        try:
            return pd.read_csv(
                input_path,
                sep=None,
                header=0,
                encoding="utf-8",
                encoding_errors="replace",
            )
        except Exception:
            pass

        with open(input_path, "rb") as f:
            raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected.get("encoding", "utf-8") or "utf-8"

        return pd.read_csv(
            input_path,
            sep=None,
            header=0,
            encoding=encoding,
            encoding_errors="replace",
        )