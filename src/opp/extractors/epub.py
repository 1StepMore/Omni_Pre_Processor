import re
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from ebooklib import epub

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    DocumentMetadata,
    ExtractionResult,
    ImageData,
    ParagraphData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError


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

        book = epub.read_epub(epub_path)

        # Get spine items in reading order
        spine_items = list(book.spine)

        # Get all image items from manifest using proper type
        image_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))

        return book, spine_items, image_items

    def _extract_cover(self, book: epub.EpubBook) -> Optional[ImageData]:
        """Extract cover image from book manifest if present."""
        import ebooklib

        # Check for cover-image relation in manifest
        for item in book.get_items():
            # Check properties for cover-image rel
            item_props = getattr(item, 'properties', set()) or set()
            if 'cover-image' in item_props:
                return ImageData(
                    data=item.get_content(),
                    mime_type=self._get_mime_type(item.get_name()),
                )

        # Check item ID and name for cover patterns
        for item in book.get_items():
            item_id = item.get_id().lower() if item.get_id() else ""
            item_name = item.get_name().lower() if item.get_name() else ""

            # Common cover naming patterns
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

            chapter_paragraphs = self._parse_html_elements(content)
            paragraphs.extend(chapter_paragraphs)

        return paragraphs

    def _parse_html_elements(self, html_content: str) -> List[ParagraphData]:
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

        for element in soup.body.children if soup.body else soup.descendants:
            if isinstance(element, str):
                text = element.strip()
                if text:
                    paragraphs.append(ParagraphData(
                        text=text,
                        style="Normal",
                        level=None,
                    ))
            elif getattr(element, 'name', None):
                tag_name = getattr(element, 'name').lower()
                element_text = element.get_text(separator=" ", strip=True)

                if not element_text:
                    continue

                if tag_name in heading_tags:
                    level = int(tag_name[1])
                    paragraphs.append(ParagraphData(
                        text=element_text,
                        style=f"Heading {level}",
                        level=level,
                    ))
                elif tag_name == 'p':
                    paragraphs.append(ParagraphData(
                        text=element_text,
                        style="Normal",
                        level=None,
                    ))

        return paragraphs

    def _extract_images(
        self, image_items: List[epub.EpubItem], cover: Optional[ImageData]
    ) -> List[ImageData]:
        """Extract all images from manifest."""
        images: List[ImageData] = []

        for item in image_items:
            try:
                content = item.get_content()
                if not content:
                    continue

                # Skip if this is the cover (already added)
                if cover and cover.data == content:
                    continue

                images.append(ImageData(
                    data=content,
                    mime_type=self._get_mime_type(item.get_name()),
                ))
            except Exception:
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