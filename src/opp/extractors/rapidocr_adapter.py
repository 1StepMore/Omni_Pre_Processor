"""Single adapter for the optional RapidOCR engine (OPP#128).

``rapidocr_onnxruntime`` exports ``RapidOCR`` — there is no
``RapidOCRSentenceExtractor`` in any released version, yet both OCR call
sites imported that name and swallowed the resulting ``ImportError`` as
"not installed", so ``--ocr-engine rapidocr`` could never run.

The engine's call shape is ``result, elapse = engine(image)`` where each
``result`` row is ``[box, text, score]`` (``None`` when nothing was
found). Everything that needs to know that shape goes through this module,
so the next upstream change is a one-file fix.
"""

from __future__ import annotations

from typing import Any

INSTALL_GUIDE = (
    "RapidOCR is not installed. "
    "Install with: pip install rapidocr-onnxruntime"
)


def load_engine() -> Any | None:
    """Return a ready RapidOCR engine, or ``None`` when the package is absent."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None

    return RapidOCR()


def recognize(engine: Any, image: Any) -> list[tuple[str, float]]:
    """Run one OCR pass and return ``(text, score)`` rows in reading order."""
    raw = engine(image)
    if not raw:
        return []

    # ``(result, elapse)`` on every release so far; tolerate a bare result
    # list so a future engine that drops the timing tuple keeps working.
    result = raw[0] if isinstance(raw, tuple) else raw

    rows: list[tuple[str, float]] = []
    for item in result or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = item[1]
        score = float(item[2]) if len(item) >= 3 else 0.0
        rows.append((str(text), score))
    return rows