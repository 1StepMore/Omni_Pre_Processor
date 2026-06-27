"""PDF to HTML extractor: converts PDF via PyMuPDF, then uses HTMLExtractor.

Used to enable the PDF -> HTML -> XLIFF -> HTML -> PDF pipeline, which
preserves images via the HTML intermediate (fitz base64-encodes images
in the HTML output, and OPP's HTMLExtractor preserves them as
data-trans-unit-id children).
"""
from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from opp.extractors.base import ExtractorBase
from opp.extractors.html import HTMLExtractor
from opp.utils.dataclasses import ExtractionResult

_logger = logging.getLogger(__name__)

DEFAULT_PDF2HTML_CSS = """\
@page { size: A4; margin: 0; }
div.page { position: relative; width: 595pt; height: 842pt; page-break-after: always; }
div.page:last-of-type { page-break-after: auto; }
body { font-family: serif; }
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

    @staticmethod
    def _fix_image_positions(page_html: str, page, doc) -> str:
        """Strip inaccurate <img> tags from PyMuPDF HTML, rebuild with correct bbox.

        PyMuPDF's ``page.get_text("html")`` emits <img> tags with CSS ``transform: matrix()``
        coordinates from the text-positioning matrix at render time, NOT the actual image bbox.
        This method replaces them with correct axis-aligned positions from ``page.get_image_info()``.
        """
        try:
            soup = BeautifulSoup(page_html, "html.parser")
        except Exception:
            return page_html

        for img_tag in soup.find_all("img"):
            img_tag.decompose()
        text_html = str(soup)

        try:
            img_infos = list(page.get_image_info())
            img_entries = list(page.get_images(full=True))
        except Exception as e:
            _logger.warning("Failed to get image info for page: %s", e)
            return text_html

        if not img_infos or not img_entries:
            return text_html

        corrected_tags: list[str] = []
        for idx in range(min(len(img_infos), len(img_entries))):
            try:
                img_info = img_infos[idx]
                bbox = img_info["bbox"]
                xref = img_entries[idx][0]

                base_image = doc.extract_image(xref)
                img_bytes = base_image.get("image")
                if not img_bytes:
                    continue
                img_ext = base_image.get("ext", "png")
                mime_type = f"image/{img_ext}"
                b64 = base64.b64encode(img_bytes).decode("ascii")

                page_h = page.rect.height
                css_left = bbox[0]
                css_top = page_h - bbox[3]
                css_w = bbox[2] - bbox[0]
                css_h = bbox[3] - bbox[1]

                img_tag = (
                    f'<img style="position:absolute;'
                    f'left:{css_left:.1f}pt;top:{css_top:.1f}pt;'
                    f'width:{css_w:.1f}pt;height:{css_h:.1f}pt;" '
                    f'src="data:{mime_type};base64,{b64}">'
                )
                corrected_tags.append(img_tag)
            except Exception as e:
                _logger.warning("Failed to correct image %d: %s", idx, e)
                continue

        if corrected_tags:
            return text_html + "\n" + "\n".join(corrected_tags)
        return text_html

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
            try:
                pw = doc[0].rect.width
                ph = doc[0].rect.height
            except Exception:
                pw, ph = 595.0, 842.0

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_raw_html = page.get_text("html")
                page_fixed = self._fix_image_positions(page_raw_html, page, doc)
                html_parts.append(f'<div class="page" style="width:{pw:.0f}pt;height:{ph:.0f}pt;">')
                html_parts.append(page_fixed)
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
