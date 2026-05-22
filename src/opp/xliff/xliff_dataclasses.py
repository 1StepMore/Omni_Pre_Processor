from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

_VALID_LANGUAGE_CODES = frozenset([
    "en", "fr", "de", "es", "it", "pt", "ru", "zh", "ja", "ko",
    "ar", "nl", "pl", "sv", "da", "fi", "no", "cs", "el", "he",
    "hu", "tr", "bg", "hr", "sk", "sl", "uk", "ro", "lt", "lv",
    "et", "sq", "mk", "be", "sr", "ka", "hy", "az", "kk",
    "uz", "tg", "tk", "mn", "ps", "fa", "ur", "th", "vi", "my",
    "km", "lo", "ne", "si", "bn", "ta", "te", "ml", "kn", "gu",
    "pa", "mr", "hi", "as", "bo", "dz", "id", "ms", "tl", "sw",
])


class XLIFFUnitState(Enum):
    UNTRANSLATED = "untranslated"
    NEEDS_TRANSLATION = "needs_translation"
    TRANSLATED = "translated"
    APPROVED = "approved"


@dataclass
class InlineElement:
    """An inline formatting element in XLIFF."""
    id: str
    type: str
    position: int
    text_covered: Optional[str] = None


@dataclass
class XLIFFTransUnit:
    id: str
    source: str
    source_language: str
    target: Optional[str] = None
    target_language: Optional[str] = None
    location: Optional[str] = None
    context: Optional[str] = None
    state: Optional[XLIFFUnitState] = None
    translate: bool = True
    inline_elements: List[InlineElement] = field(default_factory=list)


@dataclass
class XLIFFFileAttributes:
    source_language: str
    target_language: str
    original: Optional[str] = None
    datatype: str = "plaintext"
    tool_id: Optional[str] = None
    tool_version: Optional[str] = None
    xliff_version: str = "1.2"

    def __post_init__(self):
        if self.source_language not in _VALID_LANGUAGE_CODES:
            raise ValueError(
                f"Invalid source_language '{self.source_language}'. "
                f"Must be a valid ISO 639-1 code (e.g., 'en', 'fr', 'de')."
            )
        if self.target_language not in _VALID_LANGUAGE_CODES:
            raise ValueError(
                f"Invalid target_language '{self.target_language}'. "
                f"Must be a valid ISO 639-1 code (e.g., 'fr', 'de')."
            )