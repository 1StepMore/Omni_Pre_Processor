"""PDF to HTML extractor: converts PDF via PyMuPDF, then uses HTMLExtractor.

Used to enable the PDF -> HTML -> XLIFF -> HTML -> PDF pipeline, which
preserves images via the HTML intermediate (fitz base64-encodes images
in the HTML output, and OPP's HTMLExtractor preserves them as
data-trans-unit-id children).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from opp.extractors.base import ExtractorBase
from opp.extractors.html import HTMLExtractor
from opp.utils.dataclasses import ExtractionResult

_logger = logging.getLogger(__name__)

DEFAULT_PDF2HTML_CSS = """\
@page { size: A4; margin: 2cm; }
div { page-break-after: always; }
div:last-of-type { page-break-after: auto; }
body { font-family: serif; line-height: 1.6; }
"""


class PDF2HTMLExtractor(ExtractorBase):
    """Extract PDF content by converting to HTML via PyMuPDF, then parsing as HTML.

    This extractor enables exact image backfill for PDFs by routing through
    the HTML pipeline. The fitz-generated HTML has base64-embedded images
    which are preserved as <img> children in the resulting data-trans-unit-id
    nodes. ORF's xliff2html backfill then preserves these during translation.
    """

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def extract(self, input_path: Path, css: str | None = None) -> ExtractionResult:
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"PDF not found: {input_path}")

        try:
            import fitz
        except ImportError:
            raise RuntimeError(
                "PyMuPDF (fitz) is not installed. Install with: pip install pymupdf"
            )

        # Step 1: Convert PDF -> HTML via PyMuPDF
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / f"{input_path.stem}.html"
            try:
                doc = fitz.open(str(input_path))
            except Exception as e:
                raise RuntimeError(f"Failed to open PDF: {e}")

            style_content = css or DEFAULT_PDF2HTML_CSS
            html_parts = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                '<meta charset="UTF-8">',
                f"<style>{style_content}</style>",
                "</head>",
                "<body>",
            ]
            for page_num in range(len(doc)):
                page = doc[page_num]
                html_parts.append('<div class="page">')
                html_parts.append(page.get_text("html"))
                html_parts.append("</div>")
            html_parts.append("</body></html>")
            doc.close()

            pandoc_html = "\n".join(html_parts)
            html_path.write_text(pandoc_html, encoding="utf-8")

            # Step 2: Parse the HTML via HTMLExtractor to get structured content
            html_extractor = HTMLExtractor()
            result = html_extractor.extract(html_path)
            result.skeleton_html = pandoc_html
            # Format type is "html" (not "pdf") to bypass OPP's PDF->XLIFF guard
            # (pipeline.py checks result.metadata.format_type == "pdf")
            return result
