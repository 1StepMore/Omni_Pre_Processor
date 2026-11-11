"""Mechanical term-candidate extraction (OPP#116 M3).

OPP only emits STRUCTURAL candidates (frequency / first occurrence / case
variants / source coordinates); semantic filtering and ordering remain
downstream (OL ``extract_terms``). No semantic-model dependency: pure regex
over the extracted paragraph stream. v1 covers Latin-script terms only —
CJK term extraction stays with OL.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from opp.utils.dataclasses import ParagraphData

# Deterministic candidate patterns, scanned per paragraph and merged by
# position (the shapes are disjoint by construction: acronym = no lowercase,
# CamelCase = caps flip inside one word, proper sequence = 2+ Capitalized
# words). Known v1 noise: Roman numerals match the acronym pattern; a word
# after a hyphen can start a proper sequence ("Real-Time Data" -> "Time
# Data"); sentence-start articles are excluded from proper sequences (the
# match then restarts at the next word), so "The Hague" is not a candidate.
_TERM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Z][A-Z0-9]{1,}\b"),                    # API, JSON, NASA
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9]*\b"),         # GitHub, JavaScript, PostgreSQL
    re.compile(r"\b(?!The\b|An?\b)[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),  # United Nations
)


@dataclass
class TermCandidate:
    """One mechanical term candidate with its source coordinates."""

    term: str                 # canonical form (first occurrence, original casing)
    frequency: int            # occurrences of every variant across the document
    first_paragraph: int      # 0-based index into the extracted paragraph list
    first_char_offset: int    # 0-based char offset within that paragraph
    variants: list[str]       # distinct original forms, first-seen order (canonical first)


def extract_term_candidates(paragraphs: list[ParagraphData]) -> list[TermCandidate]:
    """Extract deterministic term candidates from a paragraph stream.

    Args:
        paragraphs: Extracted paragraphs in document order.

    Returns:
        Candidates sorted by frequency (desc), then first occurrence
        (paragraph, char offset) ascending. Empty list when nothing matches.
    """
    # key = casefolded surface; value = mutable candidate under construction
    found: dict[str, dict] = {}

    def _record(text: str, para_idx: int, start: int) -> None:
        key = text.casefold()
        entry = found.get(key)
        if entry is None:
            found[key] = {
                "term": text,
                "frequency": 1,
                "first_paragraph": para_idx,
                "first_char_offset": start,
                "variants": [text],
            }
        else:
            entry["frequency"] += 1
            if text not in entry["variants"]:
                entry["variants"].append(text)

    for para_idx, para in enumerate(paragraphs):
        if not para.text:
            continue
        spans: list[tuple[int, int, str]] = []
        for pattern in _TERM_PATTERNS:
            for match in pattern.finditer(para.text):
                spans.append((match.start(), match.end(), match.group(0)))
        spans.sort()
        kept_end = -1
        for start, end, text in spans:
            if start < kept_end:
                continue  # defensive: never double-count an overlapping span
            kept_end = end
            _record(text, para_idx, start)

    candidates = [TermCandidate(**entry) for entry in found.values()]
    candidates.sort(key=lambda c: (-c.frequency, c.first_paragraph, c.first_char_offset))
    return candidates


def write_terms_json(paragraphs: list[ParagraphData], path: str | Path) -> list[TermCandidate] | None:
    """Write ``terms.json`` next to the other extraction artifacts.

    Mirrors the images.json convention: the artifact is written only when
    there is content for it. Returns the candidates on write, ``None``
    (nothing written) when no candidates were found.
    """
    candidates = extract_term_candidates(paragraphs)
    if not candidates:
        return None
    payload = {"terms": [asdict(c) for c in candidates], "count": len(candidates)}
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return candidates
