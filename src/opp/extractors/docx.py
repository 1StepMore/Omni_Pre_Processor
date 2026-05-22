from dataclasses import replace
from pathlib import Path
from typing import List, Optional

import docx
import zipfile
import warnings
from docx.document import Document as DocxDocument
from docx.table import Table as DocxTable

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    RunData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class DOCXExtractor(ExtractorBase):
    def supported_extensions(self) -> List[str]:
        return [".docx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            doc: DocxDocument = docx.Document(str(input_path))
        except Exception as e:
            if "password" in str(e).lower():
                raise PasswordProtectedError(f"文件受密码保护: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        paragraphs = self.extract_paragraphs(doc)
        tables = self.extract_tables(doc)
        images = self.extract_images(doc)

        skeleton_bytes: Optional[bytes] = None
        skeleton_files: Optional[List[str]] = None
        try:
            with open(input_path, 'rb') as f:
                skeleton_bytes = f.read()
            with zipfile.ZipFile(input_path, 'r') as zf:
                key_files = [
                    'word/document.xml',      # Main document content
                    'word/styles.xml',         # Style definitions
                    'word/numbering.xml',     # Numbering definitions
                    'word/settings.xml',      # Document settings
                    '[Content_Types].xml',   # Content type declarations
                ]
                skeleton_files = [f for f in key_files if f in zf.namelist()]
        except zipfile.BadZipFile:
            warnings.append("Skeleton extraction failed: not a valid ZIP/DOCX file")
            skeleton_bytes = None
            skeleton_files = None

        if not paragraphs and not tables:
            warnings.append("文档为空")

        metadata = replace(metadata, page_count=1)

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
            skeleton=skeleton_bytes,
            skeleton_files=skeleton_files,
        )

    def extract_paragraphs(self, doc: DocxDocument) -> List[ParagraphData]:
        result: List[ParagraphData] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = para.style.name if para.style else None
            level = None

            # Handle "Heading 1", "Heading 2", etc.
            if style_name and style_name.startswith("Heading"):
                try:
                    level = int(style_name.replace("Heading ", "").replace("Heading", ""))
                except ValueError:
                    level = 1
            # Handle "Title" style -> level 1
            elif style_name == "Title":
                level = 1
            # Handle "Subtitle" style -> level 2
            elif style_name == "Subtitle":
                level = 2

            runs = self.extract_runs(para)

            result.append(ParagraphData(
                text=text,
                style=style_name,
                level=level,
                runs=runs,
            ))
        return result

    def extract_tables(self, doc: DocxDocument) -> List[TableData]:
        result: List[TableData] = []
        for table in doc.tables:
            table_data = self._parse_table(table)
            if table_data.headers or table_data.rows:
                result.append(table_data)
        return result

    def _parse_table(self, table: DocxTable) -> TableData:
        headers: List[str] = []
        rows: List[List[str]] = []

        if table.rows:
            first_row = table.rows[0]
            headers = [cell.text.strip() for cell in first_row.cells]

            for row in table.rows[1:]:
                rows.append([cell.text.strip() for cell in row.cells])

        return TableData(headers=headers, rows=rows)

    def extract_images(self, doc: DocxDocument) -> List[ImageData]:
        result: List[ImageData] = []
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_part = rel.target_part
                    image_bytes = image_part.blob
                    content_type = image_part.content_type
                    result.append(ImageData(
                        data=image_bytes,
                        mime_type=content_type,
                    ))
                except Exception:
                    continue
        return result

    def extract_runs(self, para) -> List[RunData]:
        """Extract individual runs with formatting properties from a paragraph.

        Args:
            para: python-docx Paragraph object

        Returns:
            List of RunData with text and formatting
        """
        runs = []
        for run in para.runs:
            text = run.text
            if not text or not text.strip():
                continue

            run_data = RunData(
                text=text,
                bold=bool(run.bold) if run.bold else False,
                italic=bool(run.italic) if run.italic else False,
                underline=bool(run.underline) if run.underline else False,
                strike=bool(run.font.strike) if run.font.strike else False,
            )
            runs.append(run_data)

        return runs
