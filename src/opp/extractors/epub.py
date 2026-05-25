import re
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, NavigableString
from ebooklib import epub

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    RunData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError
from opp.logger import logger


class EPUBExtractor(ExtractorBase):
    """Extracts content from EPUB files (chapters, cover, resources)."""

    def supported_extensions(self) -> List[str]:
        return [".epub"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            book, spine_items, image_items = self._parse_epub(input_path)
        except Exception as e:
            logger.warning(f"EPUB parsing failed: {e}")
            raise CorruptedFileError(f"EPUB文件损坏或无法解析: {input_path}")

        paragraphs = self._extract_chapters(book, spine_items)
        cover = self._extract_cover(book)
        images = self._extract_images(image_items, cover)

        if cover and cover not in images:
            images.insert(0, cover)

        if not paragraphs:
            warnings.append("文档为空")

        metadata = DocumentMetadata(
            file_size=metadata.file_size,
            format_type="epub",
            page_count=len(paragraphs),
        )

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],  # EPUB usually doesn't have tables
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def _parse_epub(
        self, epub_path: Path
    ) -> Tuple[epub.EpubBook, List, List[epub.EpubItem]]:
        """Parse EPUB and return book, spine items, and image items."""
        import ebooklib

        book = epub.read_epub(epub_path, options={"ignore_ncx": True})

        # Get spine items in reading order
        spine_items = list(book.spine)

        # Get all image items from manifest using proper type
        image_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))

        return book, spine_items, image_items

    def _extract_cover(self, book: epub.EpubBook) -> Optional[ImageData]:
        """Extract cover image from book manifest if present."""
        import ebooklib

        for item in book.get_items():
            item_props = getattr(item, 'properties', set()) or set()
            if 'cover-image' in item_props:
                return ImageData(
                    data=item.get_content(),
                    mime_type=self._get_mime_type(item.get_name()),
                )

        for item in book.get_items():
            item_id = item.get_id().lower() if item.get_id() else ""
            item_name = item.get_name().lower() if item.get_name() else ""

            if "cover" in item_name or "cover-image" in item_id:
                return ImageData(
                    data=item.get_content(),
                    mime_type=self._get_mime_type(item.get_name()),
                )

        return None

    def _extract_chapters(
        self, book: epub.EpubBook, spine_items: List
    ) -> List[ParagraphData]:
        """Extract chapter content from spine items in order."""
        import ebooklib

        paragraphs: List[ParagraphData] = []

        for spine_ref in spine_items:
            if isinstance(spine_ref, tuple):
                item_id = spine_ref[0]
            else:
                item_id = spine_ref

            item = book.get_item_with_id(item_id)
            if item is None:
                continue

            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            content = item.get_content()
            if not content:
                continue

            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            # Extract chapter name from item title or name, fallback to item_id
            chapter_name = item.get_title() if hasattr(item, 'get_title') and item.get_title() else None
            if not chapter_name:
                chapter_name = item.get_name() if hasattr(item, 'get_name') and item.get_name() else None
            if not chapter_name:
                chapter_name = item_id

            chapter_paragraphs = self._parse_html_elements(content, chapter=chapter_name)
            paragraphs.extend(chapter_paragraphs)

        return paragraphs

    def _parse_html_elements(self, html_content: str, chapter: Optional[str] = None) -> List[ParagraphData]:
        """Parse HTML and extract text elements as separate ParagraphData objects."""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")

        for script in soup(["script", "style"]):
            script.decompose()

        footnote_refs = soup.find_all(['a', 'span'], attrs={'role': 'doc-noteref'})
        for ref in footnote_refs:
            ref.insert_after(soup.new_string(' [[footnote]]'))

        paragraphs: List[ParagraphData] = []
        heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

        for tag in heading_tags | {'p'}:
            for element in soup.find_all(tag):
                if not _should_process_element(element, heading_tags):
                    continue
                element_text = element.get_text(separator=" ", strip=True)
                if element_text:
                    runs = self.extract_runs(element)
                    plain_text = ''.join(r.text for r in runs) if runs else element_text
                    if tag in heading_tags:
                        level = int(tag[1])
                        paragraphs.append(ParagraphData(
                            text=plain_text,
                            style=f"Heading {level}",
                            level=level,
                            chapter=chapter,
                            runs=runs,
                        ))
                    else:
                        paragraphs.append(ParagraphData(
                            text=plain_text,
                            style="Normal",
                            level=None,
                            chapter=chapter,
                            runs=runs,
                        ))

        return paragraphs

    def extract_runs(self, element) -> List[RunData]:
        runs = []
        tag_name = element.name if hasattr(element, 'name') else None

        if tag_name in ('strong', 'b', 'em', 'i', 'u', 's', 'del'):
            text = element.get_text()
            if text and text.strip():
                runs.append(RunData(
                    text=text,
                    bold=tag_name in ('strong', 'b'),
                    italic=tag_name in ('em', 'i'),
                    underline=tag_name == 'u',
                    strike=tag_name in ('s', 'del'),
                ))
            return runs

        for child in element.children:
            if hasattr(child, 'name') and child.name:
                bold = child.name in ('strong', 'b')
                italic = child.name in ('em', 'i')
                underline = child.name == 'u'
                strike = child.name in ('s', 'del')

                text = child.get_text()
                if text and text.strip():
                    runs.append(RunData(
                        text=text,
                        bold=bold,
                        italic=italic,
                        underline=underline,
                        strike=strike,
                    ))

                if child.name == 'span':
                    child_runs = self.extract_runs(child)
                    runs.extend(child_runs)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    runs.append(RunData(
                        text=text,
                        bold=False,
                        italic=False,
                        underline=False,
                        strike=False,
                    ))

        return runs

    def _extract_images(
        self, image_items: List[epub.EpubItem], cover: Optional[ImageData]
    ) -> List[ImageData]:
        """Extract all images from book manifest."""
        images: List[ImageData] = []

        for item in image_items:
            try:
                content = item.get_content()
                if not content:
                    continue

                if cover and cover.data == content:
                    continue

                images.append(ImageData(
                    data=content,
                    mime_type=self._get_mime_type(item.get_name()),
                ))
            except Exception as e:
                logger.debug(f"EPUB image extraction failed: {e}")
                continue

        return images

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename extension."""
        ext = Path(filename).suffix.lower() if filename else ""
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "application/octet-stream")


def _should_process_element(element, heading_tags):
    for child in element.children:
        if hasattr(child, 'name') and child.name in heading_tags:
            return False
    return True
