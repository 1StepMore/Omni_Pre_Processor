from pathlib import Path
from typing import List, Optional, Tuple

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
        book = epub.read_epub(epub_path)

        # Get spine items in reading order
        spine_items = list(book.spine)

        # Get all image items from manifest
        image_items = [
            item
            for item in book.get_items()
            if item.get_type() == 9  # EPUB type 9 = IMAGE
        ]

        return book, spine_items, image_items

    def _extract_cover(self, book: epub.EpubBook) -> Optional[ImageData]:
        """Extract cover image from book manifest if present."""
        # Look for cover in manifest
        for item in book.get_items():
            # Check if item is a cover image (has cover-image relation or name contains cover)
            item_id = item.get_id()
            item_name = item.get_name().lower() if item.get_name() else ""

            # Common cover naming patterns
            if "cover" in item_name or "cover-image" in item_id.lower():
                return ImageData(
                    data=item.get_content(),
                    mime_type=self._get_mime_type(item.get_name()),
                )

        # Also check via book metadata
        cover_meta = book.get_metadata("http://purl.org/dc/elements/1.1/", "coverage")
        if cover_meta:
            return None  # Not a direct image reference

        return None

    def _extract_chapters(
        self, book: epub.EpubBook, spine_items: List
    ) -> List[ParagraphData]:
        """Extract chapter content from spine items in order."""
        paragraphs: List[ParagraphData] = []

        for spine_ref in spine_items:
            # spine_ref is a tuple (item_id, linear)
            if isinstance(spine_ref, tuple):
                item_id = spine_ref[0]
            else:
                item_id = spine_ref

            # Get the item from manifest
            item = book.get_item_with_id(item_id)
            if item is None:
                continue

            # Only process HTML/XHTML content
            item_type = item.get_type()
            if item_type not in (9,):  # 7 = HTML, 9 = IMAGE... let's check actual values
                continue

            content = item.get_content()
            if not content:
                continue

            # Try to parse as HTML to extract text
            try:
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="ignore")

                # Simple text extraction - strip HTML tags
                import re
                text = re.sub(r"<[^>]+>", " ", content)
                text = re.sub(r"\s+", " ", text).strip()

                if text:
                    paragraphs.append(ParagraphData(
                        text=text,
                        style="Normal",
                        level=None,
                    ))
            except Exception:
                continue

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