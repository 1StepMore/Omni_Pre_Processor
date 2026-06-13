"""Pydantic schema for YAML frontmatter — the metadata header that OL prepends to translated Markdown files.

When OL translates a Markdown document it writes a YAML frontmatter block at the
top of the output file.  This block records the language pair, source file
reference, processor identity, and translation timestamp so that ORF can consume
the translated Markdown reliably and downstream tools can audit the pipeline.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Frontmatter(BaseModel):
    """YAML frontmatter block written by OL at the top of translated Markdown files.

    Example:
        ---
        source_lang: zh
        target_lang: en
        original_file: document.md
        processor: "OL"
        version: "0.2.6"
        translated_at: 2026-06-10T06:30:05Z
        ---

    Consumers (ORF's ``apply-md``, E2E test suite) parse this block to
    determine the language pair and verify pipeline provenance.
    """

    source_lang: str = Field(
        ...,
        description="ISO 639-1 source language code (e.g. 'zh', 'en').",
        min_length=2,
        max_length=5,
    )
    target_lang: str = Field(
        ...,
        description="ISO 639-1 target language code (e.g. 'en', 'fr').",
        min_length=2,
        max_length=5,
    )
    original_file: str = Field(
        ...,
        description="Filename (basename) of the Markdown file that was translated, for traceability.",
    )
    processor: str = Field(
        default="OL",
        description="Name of the processor that wrote this frontmatter (typically 'OL').",
    )
    version: Optional[str] = Field(
        default=None,
        description="Version of OL that produced the translation (e.g. '0.2.6').",
    )
    translated_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when the translation was completed.",
    )
    skipped: Optional[bool] = Field(
        default=None,
        description="When True, indicates the file was skipped (e.g. same-language source/target) rather than translated.",
    )

    model_config = {"extra": "ignore"}
