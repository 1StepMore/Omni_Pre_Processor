"""OPP#126: the committed OCR fixture must stay a real, decodable image.

``batch_test/phase7_email_image/normal.png`` is the input the suite's OCR
scenario (Gate 1b) drives through the real ``opp`` CLI with a real
tesseract install. It once shipped as a 114-byte truncated PNG header:
PIL raises ``unrecognized data stream contents`` and tesseract rejects the
same bytes, so the gate could never activate. Regenerate with
``python scripts/make_ocr_fixture.py``.
"""

from pathlib import Path

from PIL import Image

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "batch_test"
    / "phase7_email_image"
    / "normal.png"
)


def test_committed_ocr_fixture_decodes_as_a_full_size_image():
    assert FIXTURE.is_file(), f"missing OCR fixture: {FIXTURE}"

    with Image.open(FIXTURE) as image:
        image.load()

        # A filename-only or 1x1 placeholder still "opens"; a scanned page
        # at 150 DPI is at least A5-sized.
        assert image.width >= 1000
        assert image.height >= 1000
        assert image.mode in ("RGB", "L", "RGBA")