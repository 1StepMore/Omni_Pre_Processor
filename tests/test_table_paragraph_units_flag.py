"""OPP#80 Wave 0A: ``OPP_TABLE_PARAGRAPH_UNITS`` feature-flag helper.

The flag gates per-paragraph table units. OFF (the default) must preserve the
legacy whole-cell behavior; only ``1``/``true``/``yes``/``on`` (any case,
surrounding whitespace stripped) turn it ON.
"""

from __future__ import annotations

import pytest
from opp.config import is_table_paragraph_units_enabled


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),  # unset
        ("", False),
        ("0", False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("yes", True),
        ("YES", True),
        ("on", True),
        ("ON", True),
        ("  on  ", True),
        ("off", False),
        ("garbage", False),
    ],
)
def test_flag_truthiness(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool):
    if value is None:
        monkeypatch.delenv("OPP_TABLE_PARAGRAPH_UNITS", raising=False)
    else:
        monkeypatch.setenv("OPP_TABLE_PARAGRAPH_UNITS", value)
    assert is_table_paragraph_units_enabled() is expected


def test_flag_defaults_off_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPP_TABLE_PARAGRAPH_UNITS", raising=False)
    assert is_table_paragraph_units_enabled() is False
