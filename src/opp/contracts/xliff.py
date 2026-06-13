"""Pydantic schemas for XLIFF trans-unit structures crossing between OPP, OL, and ORF.

These models represent the logical content of an XLIFF document (version 1.2 or 2.0)
at the trans-unit level — the unit of work for translation.  They deliberately
operate at a higher level than raw XML so that all three pipeline stages can
reason about translation units without being coupled to a specific serialisation
format.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TransUnit(BaseModel):
    """A single XLIFF trans-unit — one translatable segment.

    Represents the `<trans-unit>` element from XLIFF 1.2 (or `<unit>` from
    XLIFF 2.0).  The ``id`` identifies the unit within the document, ``source``
    holds the source-language text (possibly with inline tags like ``<bx/>``),
    and ``target`` holds the translated text once OL has processed it.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this trans-unit within the XLIFF document (e.g. '1', 'seg_42').",
    )
    source: str = Field(
        ...,
        description="Source-language text, possibly containing inline formatting tags like <bx id='1' type='bold'/>.",
        min_length=0,
    )
    target: Optional[str] = Field(
        default=None,
        description="Target-language translation.  None when the unit has not been translated yet.",
    )
    note: Optional[str] = Field(
        default=None,
        description="Optional translator note or comment attached to this trans-unit (corresponds to <note> element).",
    )

    model_config = {"extra": "ignore"}


class XLIFFDocument(BaseModel):
    """Logical representation of an XLIFF document at the translation-unit level.

    Captures the document-level metadata (version, language pair) and the
    ordered list of trans-units.  This model is the unit of exchange between
    OPP (producer), OL (translator), and ORF (consumer).
    """

    version: str = Field(
        ...,
        description="XLIFF specification version ('1.2' or '2.0').",
        pattern=r"^(1\.2|2\.0)$",
        examples=["1.2", "2.0"],
    )
    source_language: str = Field(
        ...,
        description="ISO 639-1 source language code (e.g. 'zh', 'en').",
        min_length=2,
        max_length=5,
    )
    target_language: str = Field(
        ...,
        description="ISO 639-1 target language code (e.g. 'en', 'fr').",
        min_length=2,
        max_length=5,
    )
    units: list[TransUnit] = Field(
        default_factory=list,
        description="Ordered list of trans-units in document order.",
    )

    model_config = {"extra": "ignore"}
