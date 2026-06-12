import logging
import re
from pathlib import Path
from typing import List

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ParagraphData
from opp.error_handler import ExtractionError

logger = logging.getLogger(__name__)

_YOUTUBE_URL_PATTERNS = [
    re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+"),
    re.compile(r"^https?://youtu\.be/[\w-]+"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/embed/[\w-]+"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/[\w-]+"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/live/[\w-]+"),
]


def _is_valid_youtube_url(url: str) -> bool:
    return any(pattern.match(url) for pattern in _YOUTUBE_URL_PATTERNS)


def _extract_url_from_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for line in content.splitlines():
        if line.startswith("URL="):
            return line[4:].strip()
    raise ExtractionError(f"No URL found in .url file: {path}")


class YouTubeExtractor(ExtractorBase):
    def supported_extensions(self) -> list[str]:
        return [".url"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        url = _extract_url_from_file(input_path)

        if not _is_valid_youtube_url(url):
            raise ExtractionError(f"Invalid YouTube URL: {url}")

        try:
            from markitdown import MarkItDown
        except ImportError:
            raise ExtractionError(
                "markitdown is required for YouTube extraction. "
                "Install it with: pip install markitdown[youtube-transcription]"
            )

        try:
            md = MarkItDown()
            result = md.convert(url)
            text_content = result.text_content
        except Exception as e:
            logger.warning(f"YouTube extraction failed for {url}: {e}")
            return ExtractionResult(
                paragraphs=[],
                tables=[],
                images=[],
                warnings=[f"YouTube extraction failed: {str(e)}"],
                metadata=DocumentMetadata(
                    file_size=input_path.stat().st_size,
                    format_type="youtube",
                ),
            )

        paragraphs = self._parse_transcript(text_content, url)

        if not paragraphs:
            logger.warning(f"No transcript found for YouTube video: {url}")

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=DocumentMetadata(
                file_size=input_path.stat().st_size,
                format_type="youtube",
            ),
        )

    def _parse_transcript(self, text_content: str, _url: str) -> list[ParagraphData]:
        if not text_content:
            return []

        paragraphs = []
        lines = text_content.split("\n")
        in_transcript = False

        for line in lines:
            stripped = line.strip()
            if stripped == "### Transcript":
                in_transcript = True
                continue
            if in_transcript and stripped.startswith("### "):
                break
            if in_transcript and stripped:
                paragraphs.append(
                    ParagraphData(text=stripped, level=0, style="Normal")
                )

        if not paragraphs and text_content.strip():
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    paragraphs.append(
                        ParagraphData(text=stripped, level=0, style="Normal")
                    )

        return paragraphs