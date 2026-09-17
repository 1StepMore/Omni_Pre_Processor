from pathlib import Path

from opp.extractors.base import ExtractorBase
from opp.logger import logger
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError


class IPYNBExtractor(ExtractorBase):

    def supported_extensions(self) -> list[str]:
        return [".ipynb"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)

        try:
            import nbformat
        except ImportError:
            raise CorruptedFileError(
                "nbformat is required to extract Jupyter notebooks. "
                "Install it with: pip install nbformat"
            )

        try:
            with open(input_path, encoding="utf-8") as f:
                notebook = nbformat.read(f, as_version=4)
        except Exception:
            logger.debug("Cannot parse notebook file: %s", input_path)
            raise CorruptedFileError(f"Cannot parse notebook file: {input_path}")

        paragraphs: list[ParagraphData] = []

        for cell in notebook.cells:
            cell_type = cell.cell_type
            source = cell.source
            if isinstance(source, list):
                source = "".join(source)

            if cell_type == "markdown":
                # Markdown headings at root level = level 1
                paragraphs.append(
                    ParagraphData(
                        text=source or "",
                        style="Markdown",
                        level=1,
                    )
                )
            elif cell_type == "code":
                text = source or ""
                outputs = getattr(cell, "outputs", [])
                if outputs:
                    output_lines = []
                    for output in outputs:
                        if hasattr(output, "text") and output.text:
                            output_lines.append(f"# Output: {output.text}")
                        elif hasattr(output, "data") and output.data:
                            output_lines.append(f"# Data: {output.data}")
                        elif hasattr(output, "output_type"):
                            output_lines.append(f"# [{output.output_type}]")
                    if output_lines:
                        text = source + "\n" + "\n".join(output_lines)
                paragraphs.append(
                    ParagraphData(
                        text=text,
                        style="Code",
                        level=0,
                    )
                )

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=DocumentMetadata(format_type="ipynb"),
        )
