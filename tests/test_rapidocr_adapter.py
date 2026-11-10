"""Regression lock for OPP#128: RapidOCR engine name and call shape.

The published API is ``from rapidocr_onnxruntime import RapidOCR`` and
``result, elapse = engine(image)``. Both OPP call sites used to import a
nonexistent ``RapidOCRSentenceExtractor``, which silently degraded the
``--ocr-engine rapidocr`` path to "not installed".
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from opp.extractors import rapidocr_adapter
from opp.extractors.image_ocr import ImageOCRExtractor
from opp.extractors.pdf import PDFExtractor

ROWS = [
    [[[0, 0], [10, 0], [10, 5], [0, 5]], "first line", 0.97],
    [[[0, 8], [10, 8], [10, 13], [0, 13]], "second line", 0.90],
]


def _fake_module(monkeypatch, rows=ROWS):
    """Install a stand-in exposing the real public surface: ``RapidOCR``."""
    calls: list[str] = []

    class RapidOCR:
        def __init__(self):
            calls.append("__init__")

        def __call__(self, image):
            calls.append("call")
            return rows, [0.01]

    module = types.ModuleType("rapidocr_onnxruntime")
    module.RapidOCR = RapidOCR
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", module)
    return calls


def test_load_engine_uses_public_class(monkeypatch):
    calls = _fake_module(monkeypatch)

    engine = rapidocr_adapter.load_engine()

    assert engine is not None
    assert calls == ["__init__"]


def test_load_engine_returns_none_when_package_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)

    assert rapidocr_adapter.load_engine() is None


def test_recognize_unpacks_timing_tuple(monkeypatch):
    _fake_module(monkeypatch)
    engine = rapidocr_adapter.load_engine()

    assert rapidocr_adapter.recognize(engine, "page.png") == [
        ("first line", 0.97),
        ("second line", 0.90),
    ]


@pytest.mark.parametrize("rows", [None, []])
def test_recognize_returns_empty_without_text(monkeypatch, rows):
    _fake_module(monkeypatch, rows=rows)
    engine = rapidocr_adapter.load_engine()

    assert rapidocr_adapter.recognize(engine, "page.png") == []


def test_image_extractor_joins_rapidocr_rows(monkeypatch, tmp_path: Path):
    _fake_module(monkeypatch)
    monkeypatch.setenv("OPP_OCR_ENGINE", "rapidocr")
    image_path = tmp_path / "page.png"
    Image.new("RGB", (200, 80), "white").save(image_path)

    result = ImageOCRExtractor().extract(image_path)

    assert [p.text for p in result.paragraphs] == ["first line\nsecond line"]


def test_pdf_ocr_rapidocr_joins_rows(monkeypatch):
    _fake_module(monkeypatch)
    extractor = PDFExtractor()
    engine = rapidocr_adapter.load_engine()

    text = extractor._ocr_rapidocr(Image.new("RGB", (200, 80), "white"), engine)

    assert text == "first line\nsecond line"