#!/usr/bin/env python3
"""Regenerate the committed OCR fixture (OPP#126).

``batch_test/phase7_email_image/normal.png`` used to be a truncated
114-byte PNG header with no image data: PIL raises ``unrecognized data
stream contents`` and tesseract (the engine the suite's Gate 1b installs)
rejects the same bytes.  This script writes a synthetic, text-bearing
"scan" in its place — deterministic output, fictional content, no
personal data — so the OCR path can be exercised with a real engine.

Run from the OPP repo root (requires Pillow, already an OPP dependency):

    python scripts/make_ocr_fixture.py

The fixture is A4 at 150 DPI (~1.3k x 1.7k, well under the 500 KB cap)
with a 0.4 px blur so it reads as a scan rather than a rendered PDF
while staying comfortably legible to tesseract.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "batch_test" / "phase7_email_image" / "normal.png"

# A4 at 150 DPI.
WIDTH, HEIGHT = 1240, 1754
MARGIN = 90
DPI = (150, 150)

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
)
FONT_CANDIDATES_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)

BODY_LINES = [
    "Vendor: Contoso Supply Ltd.",
    "Ship to: 1420 Harbor Way, Springfield",
    "Order date: 2026-03-14",
    "",
    "Please supply the following line items and confirm availability",
    "within two business days. Partial shipments are acceptable if the",
    "remaining quantity arrives before the end of the month.",
]

TABLE_ROWS = [
    ("1", "A4 copy paper, 5 reams", "42.00"),
    ("2", "Toner cartridge, black", "89.50"),
    ("3", "Desk organizer, oak", "31.25"),
]


def _load_font(candidates: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    # Pillow >= 10 ships a scalable default font.
    return ImageFont.load_default(size=size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build() -> Path:
    title_font = _load_font(FONT_CANDIDATES_BOLD, 34)
    subtitle_font = _load_font(FONT_CANDIDATES, 22)
    body_font = _load_font(FONT_CANDIDATES, 21)
    mono_font = _load_font(FONT_CANDIDATES, 20)
    footer_font = _load_font(FONT_CANDIDATES, 16)

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    draw.rectangle(
        [MARGIN // 2, MARGIN // 2, WIDTH - MARGIN // 2, HEIGHT - MARGIN // 2],
        outline=(190, 190, 190),
        width=2,
    )

    y = MARGIN
    draw.text((MARGIN, y), "NORTHWIND TRADERS", font=title_font, fill=(20, 20, 20))
    y += 52
    draw.text(
        (MARGIN, y),
        "Purchase Order PO-2026-0042",
        font=subtitle_font,
        fill=(60, 60, 60),
    )
    y += 46
    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=(120, 120, 120), width=2)
    y += 34

    text_width = WIDTH - 2 * MARGIN
    for line in BODY_LINES:
        if not line:
            y += 18
            continue
        for wrapped in _wrap(line, body_font, text_width):
            draw.text((MARGIN, y), wrapped, font=body_font, fill=(25, 25, 25))
            y += 30

    y += 26
    col_qty, col_desc, col_amount = MARGIN, MARGIN + 60, WIDTH - MARGIN - 110
    draw.text((col_qty, y), "Qty", font=mono_font, fill=(40, 40, 40))
    draw.text((col_desc, y), "Description", font=mono_font, fill=(40, 40, 40))
    draw.text((col_amount, y), "Amount", font=mono_font, fill=(40, 40, 40))
    y += 32
    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=(120, 120, 120), width=1)
    y += 14

    for qty, desc, amount in TABLE_ROWS:
        draw.text((col_qty, y), qty, font=mono_font, fill=(25, 25, 25))
        draw.text((col_desc, y), desc, font=mono_font, fill=(25, 25, 25))
        draw.text((col_amount, y), amount, font=mono_font, fill=(25, 25, 25))
        y += 32

    y += 6
    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=(120, 120, 120), width=1)
    y += 14
    draw.text((col_desc, y), "Subtotal", font=mono_font, fill=(25, 25, 25))
    draw.text((col_amount, y), "162.75", font=mono_font, fill=(25, 25, 25))
    y += 52

    for wrapped in _wrap(
        "Questions about this order: orders@northwind.example",
        body_font,
        text_width,
    ):
        draw.text((MARGIN, y), wrapped, font=body_font, fill=(25, 25, 25))
        y += 30

    draw.text(
        (WIDTH // 2 - 40, HEIGHT - MARGIN),
        "Page 1 of 1",
        font=footer_font,
        fill=(90, 90, 90),
    )

    # Scanner-ish softness: keeps glyphs far above tesseract's threshold.
    image = image.filter(ImageFilter.GaussianBlur(radius=0.4))

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    image.save(FIXTURE, format="PNG", dpi=DPI, optimize=True)
    return FIXTURE


def main() -> int:
    path = build()
    size = path.stat().st_size
    if size > 500 * 1024:
        print(f"FIXTURE TOO LARGE: {size} bytes > 512000", file=sys.stderr)
        return 1
    with Image.open(path) as check:
        check.load()
        print(f"wrote {path.relative_to(REPO_ROOT)}: {check.size[0]}x{check.size[1]} "
              f"{check.mode} {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())