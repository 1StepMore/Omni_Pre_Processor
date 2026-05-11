from enum import Enum
from pathlib import Path
from typing import Tuple


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
    UNKNOWN = "unknown"


def detect_format(path: Path) -> Tuple[FormatType, float]:
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
        except Exception:
            pass
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
    except Exception:
        pass

    # Extension-based HTML fallback
    ext = path.suffix.lower()
    if ext in (".html", ".htm"):
        return (FormatType.HTML, 0.5)

    return (FormatType.UNKNOWN, 0.0)
