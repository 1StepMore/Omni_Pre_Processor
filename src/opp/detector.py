from enum import Enum
from pathlib import Path
from typing import Tuple


class FormatType(Enum):
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
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

    return (FormatType.UNKNOWN, 0.0)
