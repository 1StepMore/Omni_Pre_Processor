"""Contract: extractor-declared input suffixes must be MCP-allowed (minus exemptions).

Regression guard for OPP #88 (``.ipynb`` was extractor-supported but
MCP-denied: ``OPP_PATH_DENIED: Extension '.ipynb' not in allowed set``).

The test auto-discovers every :class:`ExtractorBase` subclass under
``opp.extractors`` and asserts::

    {declared suffixes} - EXEMPT ⊆ PathValidator.ALLOWED_EXTENSIONS

so any future "extractor supports / MCP rejects" drift fails in CI
instead of being found by hand.

Explicit exemptions (intentionally not MCP-exposed, do NOT "fix" by
adding them to the whitelist without a security review):

- ``MEDIA_EXEMPT`` — image/audio/video formats. Pre-existing policy:
  the MCP surface does not accept raw media uploads.
- ``NETWORK_EXEMPT`` — ``.url`` triggers outbound YouTube transcription
  (network + API side effects); intentionally not MCP-exposed.
"""

import importlib
import pkgutil

import opp.extractors as _extractors_pkg
from opp.extractors.base import ExtractorBase
from opp.mcp.security import PathValidator

# Media formats: extractor-supported but intentionally MCP-blocked (pre-existing policy).
MEDIA_EXEMPT: set[str] = {
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
    ".wav", ".mp3", ".mp4",
}

# Pseudo-formats with network side effects: intentionally MCP-blocked.
NETWORK_EXEMPT: set[str] = {".url"}

EXEMPT: set[str] = MEDIA_EXEMPT | NETWORK_EXEMPT


def _discover_extractor_extensions() -> dict[str, set[str]]:
    """Import every ``opp.extractors`` submodule and map class name -> suffixes."""
    for mod in pkgutil.walk_packages(
        _extractors_pkg.__path__, prefix=f"{_extractors_pkg.__name__}."
    ):
        importlib.import_module(mod.name)
    mapping: dict[str, set[str]] = {}
    for cls in ExtractorBase.__subclasses__():
        # All concrete extractors are no-arg constructible (see OPPPipeline
        # registry in src/opp/pipeline.py). Fail loudly otherwise so a new
        # extractor with ctor args updates this contract deliberately.
        exts = {e.lower() for e in cls().supported_extensions()}
        mapping.setdefault(cls.__name__, set()).update(exts)
    return mapping


def test_extractor_extensions_covered_by_mcp_whitelist():
    mapping = _discover_extractor_extensions()
    assert mapping, "no ExtractorBase subclasses discovered — check imports"

    declared: set[str] = set().union(*mapping.values())
    allowed = {e.lower() for e in PathValidator.ALLOWED_EXTENSIONS}
    missing = {e for e in declared if e not in EXEMPT} - allowed

    assert not missing, (
        "extractor-supported suffix(es) rejected by MCP whitelist: "
        f"{sorted(missing)}; per-class map={mapping}, "
        f"EXEMPT={sorted(EXEMPT)}"
    )


def test_issue_88_ipynb_tsv_msg_allowed():
    """Pin the OPP #88 fix: .ipynb / .tsv / .msg must be MCP-allowed."""
    allowed = {e.lower() for e in PathValidator.ALLOWED_EXTENSIONS}
    assert {".ipynb", ".tsv", ".msg"} <= allowed
