"""Pipeline artifact schemas (OPP → OL → ORF contracts).

These Pydantic models define the data structures that cross module boundaries
in the Omni Localization Suite pipeline.  All three modules — OPP
(Omni-Pre-Processor), OL (Omni-Localizer), and ORF (Omni-Re-Formatter) —
can import from ``opp.contracts`` to validate, produce, or consume these
artifacts without coupling to each other's internal implementations.

Models
------
- ``ImageEntry`` / ``ImageManifest`` — ``images.json`` (OPP → ORF)
- ``SourceInfo`` / ``Manifest`` — ``manifest.json`` (OPP → ORF, OL)
- ``TransUnit`` / ``XLIFFDocument`` — XLIFF trans-unit structures (OPP → OL → ORF)
- ``Frontmatter`` — YAML frontmatter block in translated Markdown (OL → ORF)
"""

from opp.contracts.frontmatter import Frontmatter
from opp.contracts.images import ImageEntry, ImageManifest
from opp.contracts.manifest import Manifest, SourceInfo
from opp.contracts.xliff import TransUnit, XLIFFDocument

__all__ = [
    "Frontmatter",
    "ImageEntry",
    "ImageManifest",
    "Manifest",
    "SourceInfo",
    "TransUnit",
    "XLIFFDocument",
]
