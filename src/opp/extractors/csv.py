from pathlib import Path

import chardet
import pandas as pd

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    ExtractionResult,
    ParagraphData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError
from opp.logger import logger


class CSVExtractor(ExtractorBase):
    def supported_extensions(self) -> list[str]:
        return [".csv", ".tsv"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        df = self._read_csv_with_encoding(input_path)

        row_count = len(df)
        if row_count > 10000:
            warnings.append(f"文件行数较多 ({row_count} 行)，可能影响处理性能")

        headers = df.columns.tolist()

        max_cols = df.shape[1]
        padded_rows = []
        for _, row in df.iterrows():
            padded_row = ["" if pd.isna(v) else str(v) for v in row.values]
            while len(padded_row) < max_cols:
                padded_row.append("")
            padded_rows.append(padded_row)

        # Summary paragraph instead of tab-separated rows (tables handle formatting in MarkdownGenerator)
        if padded_rows:
            summary = f"CSV file with {len(headers)} columns and {len(padded_rows)} data rows"
            paragraphs = [ParagraphData(text=summary)]
        else:
            paragraphs = []

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

    def extract_tables(self, input_path: Path) -> list[TableData]:
        """Extract tables from a CSV file.

        Args:
            input_path: Path to the CSV file.

        Returns:
            List of TableData objects (CSV typically has one table per file).
        """
        self.validate_file(input_path)
        df = self._read_csv_with_encoding(input_path)

        headers = df.columns.tolist()
        max_cols = df.shape[1]
        padded_rows = []
        for _, row in df.iterrows():
            padded_row = ["" if pd.isna(v) else str(v) for v in row.values]
            while len(padded_row) < max_cols:
                padded_row.append("")
            padded_rows.append(padded_row)

        return [
            TableData(
                headers=[str(h) for h in headers],
                rows=padded_rows,
            )
        ]

    def _detect_header(self, input_path: Path) -> int | None:
        with open(input_path, "rb") as f:
            raw_first = f.readline()
        try:
            first_line = raw_first.decode("utf-8", errors="replace").strip()
        except Exception as e:
            logger.debug(f"CSV header decode failed: {e}")
            return 0
        sep = self._detect_separator(first_line)
        if not sep:
            if "," not in first_line and "\t" not in first_line:
                if "\n" in first_line or first_line.count(",") == 0:
                    return None
            return 0
        parts = first_line.split(sep)
        if len(parts) < 2:
            return None
        try:
            float(parts[0].strip())
            float(parts[1].strip())
            return None
        except ValueError:
            return 0

    def _detect_separator(self, first_line: str) -> str | None:
        if "\t" in first_line and first_line.count("\t") >= 2:
            return "\t"
        if "," in first_line:
            return ","
        return None

    def _read_csv_with_encoding(self, input_path: Path) -> pd.DataFrame:
        with open(input_path, "rb") as f:
            raw_data = f.read()
        if self._is_likely_binary(raw_data):
            raise CorruptedFileError(f"文件似乎是二进制格式，不是CSV: {input_path}")

        encoding, fallback_enc = self._detect_encoding(input_path)

        with open(input_path, "rb") as f:
            raw_first = f.readline()
        first_line = raw_first.decode("utf-8", errors="replace").strip()
        detected_sep = self._detect_separator(first_line)
        header = self._detect_header(input_path)

        if detected_sep:
            sep_order = [detected_sep, ",", "\t", None]
        else:
            sep_order = [",", None]

        for sep in sep_order:
            try:
                actual_header = header if sep is not None else 0
                df = pd.read_csv(
                    input_path,
                    sep=sep,
                    engine="python",
                    header=actual_header,
                    encoding=encoding,
                    encoding_errors="replace",
                    on_bad_lines="skip",
                )
                if sep == "," and header is None and df.shape[1] == 1 and len(df) > 1:
                    df2 = pd.read_csv(
                        input_path,
                        sep=",",
                        engine="python",
                        header=0,
                        encoding=encoding,
                        encoding_errors="replace",
                        on_bad_lines="skip",
                    )
                    if len(df2) < len(df):
                        return df2
                return df
            except Exception as e:
                logger.debug(f"CSV read with separator '{sep}' failed: {e}")
                continue

        try:
            return pd.read_csv(
                input_path,
                sep=",",
                engine="python",
                header=0,
                encoding=fallback_enc,
                encoding_errors="replace",
                on_bad_lines="skip",
            )
        except Exception as e:
            logger.debug(f"CSV read with fallback encoding failed: {e}")
            df = pd.read_csv(
                input_path,
                sep=None,
                engine="python",
                header=None,
                encoding=encoding,
                encoding_errors="replace",
            )
            if df.empty:
                raise CorruptedFileError(f"无法解析CSV文件: {input_path}")
            return df

    def _is_likely_binary(self, raw_data: bytes) -> bool:
        if len(raw_data) == 0:
            return True
        if raw_data[:4] in (b'\x89PNG', b'\xff\xd8\xff', b'%PDF', b'GIF8', b'RIFF'):
            return True
        # 2026-06-18 round 14 #2: count CJK + extended-Latin UTF-8 bytes as
        # printable. The previous ASCII-only check (32-126) false-positived
        # on Chinese/Japanese/Korean content: a 3-byte UTF-8 sequence like
        # 风冷无霜 has 0 printable bytes by the old metric, tripping the 0.5
        # threshold and rejecting perfectly valid CJK CSV files.
        printable = 0
        i = 0
        sample = raw_data[:2048]
        n = len(sample)
        while i < n:
            b = sample[i]
            if 32 <= b <= 126 or b in (9, 10, 13):
                printable += 1
                i += 1
            elif b < 0x80:
                printable += 1
                i += 1
            else:
                # Count UTF-8 multi-byte sequences as 1 printable char each.
                # Skip continuation bytes (10xxxxxx = 0x80-0xBF).
                if 0xC0 <= b <= 0xF7:
                    printable += 1
                    i += 1
                    while i < n and (sample[i] & 0xC0) == 0x80:
                        i += 1
                else:
                    i += 1
        total = n
        if total == 0:
            return True
        ratio = printable / total
        return ratio < 0.3

    def _detect_encoding(self, input_path: Path):
        with open(input_path, "rb") as f:
            raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        return encoding, encoding
