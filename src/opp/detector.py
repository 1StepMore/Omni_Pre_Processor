from enum import Enum
from pathlib import Path
import re
from typing import Tuple, Union

from opp.logger import logger

YOUTUBE_URL_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|shorts/|live/)?[\w-]+"
)


def _is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube URL (watch, embed, shorts, or live)."""
    return bool(YOUTUBE_URL_PATTERN.match(url))


class FormatType(Enum):
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    HTML = "html"
    EPUB = "epub"
    EMAIL = "email"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    IPYNB = "ipynb"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


def detect_format(path: Path | str) -> tuple[FormatType, float]:
    if isinstance(path, str):
        path = Path(path)

    try:
        with open(path, "rb") as f:
            header = f.read(8)
    except FileNotFoundError:
        return (FormatType.UNKNOWN, 0.0)

    if header.startswith(b"PK"):
        ext = path.suffix.lower()
        if ext == ".docx":
            return (FormatType.DOCX, 1.0)
        elif ext == ".pptx":
            return (FormatType.PPTX, 1.0)
        elif ext == ".xlsx":
            return (FormatType.XLSX, 1.0)
        elif ext == ".epub":
            return (FormatType.EPUB, 1.0)
        elif ext in (".doc", ".docm"):
            return (FormatType.DOCX, 0.5)
        elif ext == ".potx":
            return (FormatType.PPTX, 0.5)
        return (FormatType.UNKNOWN, 0.0)

    if header.startswith(b"%PDF"):
        return (FormatType.PDF, 1.0)

    ext = path.suffix.lower()
    if ext == ".pdf":
        return (FormatType.PDF, 0.5)
    elif ext in (".docx", ".doc", ".docm"):
        return (FormatType.DOCX, 0.5)
    elif ext in (".pptx", ".potx", ".pptm"):
        return (FormatType.PPTX, 0.5)
    elif ext == ".xlsx":
        return (FormatType.XLSX, 1.0)
    elif ext == ".csv":
        return (FormatType.CSV, 1.0)
    elif ext == ".json":
        return (FormatType.JSON, 1.0)
    elif ext == ".xml":
        return (FormatType.XML, 1.0)
    elif ext == ".ipynb":
        # 2026-06-18 round 14 #4: check .ipynb extension FIRST. The .ipynb
        # file IS valid JSON (notebook is a JSON array of cells), so the
        # "first byte is { or [" check at the bottom of this function
        # would otherwise misclassify it as JSON. The IPYNBExtractor is
        # wired in pipeline.py:72 and produces proper cells/code extraction.
        return (FormatType.IPYNB, 1.0)

    # JSON detection: UTF-8 BOM or first char { or [ (no extension case)
    if header.startswith(b"\xef\xbb\xbf"):
        # UTF-8 BOM present at start, check first actual char
        try:
            with open(path, "rb") as f:
                # Skip BOM (3 bytes) and read first char after
                f.read(3)
                first_byte = f.read(1)
                if first_byte in (b"{", b"["):
                    return (FormatType.JSON, 1.0)
        except Exception as e:
            logger.warning(f"JSON detection failed: {e}")
    else:
        # No BOM, check if first byte is { or [
        if header[0:1] in (b"{", b"["):
            return (FormatType.JSON, 1.0)

    # XML detection: starts with <?xml (case-insensitive, no extension case)
    if header.startswith(b"<?xml") or header.startswith(b"<?XML") or header.startswith(b"<?Xml") or header.startswith(b"<?xMl"):
        return (FormatType.XML, 1.0)

    # HTML detection: check for <!DOCTYPE html> or <html> tag start
    try:
        with open(path, "rb") as f:
            content_start = f.read(1024).lower()
            if b"<!doctype html" in content_start or b"<html" in content_start:
                ext = path.suffix.lower()
                if ext in (".html", ".htm"):
                    return (FormatType.HTML, 1.0)
                return (FormatType.HTML, 0.9)
    except Exception as e:
        logger.warning(f"HTML detection failed: {e}")

    # Extension-based HTML fallback
    ext = path.suffix.lower()
    if ext in (".html", ".htm"):
        return (FormatType.HTML, 0.5)

    # Email format detection
    if ext in (".eml", ".msg"):
        return (FormatType.EMAIL, 1.0)

    # Image format detection
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return (FormatType.IMAGE, 1.0)

    # WAV audio detection: RIFF header + WAVE form type at bytes 8-11
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
                return (FormatType.AUDIO, 1.0)
    except Exception as e:
        logger.warning(f"AUDIO detection failed: {e}")

    # MP3 audio detection: ID3 prefix (ID3v2) or bytes 0-2 match ID3v2 pattern
    try:
        with open(path, "rb") as f:
            header = f.read(3)
            if header.startswith(b"ID3") or (len(header) >= 2 and header[0] in (0xFF,) and header[1] in (0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF)):
                ext = path.suffix.lower()
                if ext in (".mp3", ".mp2", ".mp1"):
                    return (FormatType.AUDIO, 1.0)
                return (FormatType.AUDIO, 0.8)
    except Exception as e:
        logger.warning(f"MP3 detection failed: {e}")

    # MP4 video detection: ftyp box at start (bytes 4-7 = "ftyp")
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if header[4:8] == b"ftyp":
                return (FormatType.VIDEO, 1.0)
    except Exception as e:
        logger.warning(f"VIDEO detection failed: {e}")

    # IPYNB detection: extension + JSON structure with ipynb nbformat mimetype
    if ext == ".ipynb":
        try:
            with open(path, "rb") as f:
                content = f.read()
                if b'"nbformat"' in content and b'"ipynb"' in content:
                    return (FormatType.IPYNB, 1.0)
                # Fallback: valid JSON with cells key
                if b'"cells"' in content:
                    return (FormatType.IPYNB, 0.9)
        except Exception as e:
            logger.warning(f"IPYNB detection failed: {e}")
        return (FormatType.IPYNB, 0.5)

    # YouTube .url file detection
    if ext == ".url":
        try:
            with open(path, encoding="utf-8") as f:
                first_line = f.readline().strip()
            if first_line.startswith("URL=") and _is_youtube_url(first_line[4:]):
                return (FormatType.YOUTUBE, 1.0)
        except (OSError, UnicodeDecodeError):
            pass

    # YouTube URL detection
    youtube_pattern = re.compile(
        r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)[\w-]+"
    )
    if youtube_pattern.match(str(path)):
        return (FormatType.YOUTUBE, 1.0)

    return (FormatType.UNKNOWN, 0.0)
