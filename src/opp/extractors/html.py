import base64
import re
from pathlib import Path
from typing import List, Optional

from lxml import html

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ImageData
from opp.utils.exceptions import CorruptedFileError


class HTMLExtractor(ExtractorBase):

    def supported_extensions(self) -> List[str]:
        return [".html", ".htm"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: List[str] = []

        try:
            content = input_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = input_path.read_text(encoding="latin-1")
            except Exception as e:
                raise CorruptedFileError(f"无法读取HTML文件: {input_path}")

        metadata = DocumentMetadata(
            file_size=metadata.file_size,
            format_type="html",
        )

        if self._detect_js_heavy(content):
            warnings.append("JS-rendered page detected")

        images = self._extract_images(content, input_path.parent)

        return ExtractionResult(
            paragraphs=[],
            tables=[],
            images=images,
            metadata=metadata,
            warnings=warnings,
        )

    def _extract_images(self, html_content: str, base_dir: Path) -> List[ImageData]:
        result: List[ImageData] = []

        try:
            tree = html.fromstring(html_content)
        except Exception:
            return result

        for img in tree.xpath("//img[@src]"):
            src = img.get("src", "")
            if not src:
                continue

            if src.startswith(("http://", "https://", "//")):
                continue

            if src.startswith("data:"):
                image_data = self._parse_data_uri(src)
                if image_data:
                    result.append(image_data)
                continue

            try:
                img_path = base_dir / src if not Path(src).is_absolute() else Path(src)
                if img_path.exists():
                    data = img_path.read_bytes()
                    mime_type = self._guess_mime_type(src)
                    result.append(ImageData(data=data, mime_type=mime_type))
            except Exception:
                continue

        return result

    def _parse_data_uri(self, src: str) -> Optional[ImageData]:
        match = re.match(r"data:([^;]+);base64,(.+)$", src)
        if not match:
            return None

        mime_type = match.group(1)
        data_str = match.group(2)

        try:
            data = base64.b64decode(data_str)
            return ImageData(data=data, mime_type=mime_type)
        except Exception:
            return None

    def _guess_mime_type(self, src: str) -> str:
        ext = Path(src).suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        return mime_map.get(ext, "application/octet-stream")

    def _detect_js_heavy(self, html_content: str) -> bool:
        js_indicators = [
            r"react",
            r"vue",
            r"angular",
            r"ember\.js",
            r"mithril\.js",
            r"preact",
            r"solid\.js",
            r"svelte",
            r"jquery",
            r"prototype\.js",
            r"dojo",
            r"ext\.js",
            r" mootools",
            r"scriptaculous",
            r"node_modules",
            r"webpack",
            r"vite",
            r"next\.js",
            r"nuxt",
            r"gatsby",
            r"11ty",
            r"jekyll",
            r"hugo",
            r"angular\.js",
            r"underscore\.js",
            r"lazy\.js",
            r" lodash",
        ]

        content_lower = html_content.lower()
        for pattern in js_indicators:
            if re.search(pattern, content_lower):
                return True

        script_tags = re.findall(r"<script[^>]*>", html_content)
        for tag in script_tags:
            if "src=" in tag and len(tag) > 50:
                return True

        return False