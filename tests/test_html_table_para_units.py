"""OPP#80 Wave 2: HTML per-paragraph table units behind ``OPP_TABLE_PARAGRAPH_UNITS``.

With the flag OFF a non-empty ``<td>``/``<th>`` stays one space-joined bare
unit (legacy). With it ON, a cell with >= 2 direct block-level children and no
stray inline text emits one ``_para{p}`` unit per non-empty block group; the
group model must match ORF's HTML writer index-for-index.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from opp.extractors.html import (
    _TABLE_CELL_BLOCK_TAGS,
    HTMLExtractor,
    _is_table_cell_block,
    _table_cell_paragraph_groups,
)
from opp.utils.dataclasses import TableCellData
from opp.xliff import XLIFFFileGenerator

_FLAG = "OPP_TABLE_PARAGRAPH_UNITS"


def _wrap(cell_inner: str) -> str:
    return f"<html><body><table><tr><td>{cell_inner}</td></tr></table></body></html>"


def _cells(cell_inner: str) -> list[TableCellData]:
    return HTMLExtractor()._extract_table_cells(_wrap(cell_inner))


def _generate_xliff(cell_inner: str, tmp_path: Path) -> bytes:
    html_path = tmp_path / "doc.html"
    html_path.write_text(_wrap(cell_inner), encoding="utf-8")
    result = HTMLExtractor().extract(html_path)
    out_path = tmp_path / "out.xlf"
    XLIFFFileGenerator.from_extraction_result(result, "en", "zh").write_to_file(out_path)
    return out_path.read_bytes()


def _table_resnames(xliff_bytes: bytes) -> list[str]:
    names = [r.decode("utf-8") for r in re.findall(rb'resname="([^"]+)"', xliff_bytes)]
    return [name for name in names if name.startswith("table_")]


def test_flag_off_is_legacy_space_joined_single_unit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(_FLAG, raising=False)
    cells = _cells("<p>P0</p><p>P1</p><p>P2</p>")

    assert len(cells) == 1
    assert cells[0].text == "P0 P1 P2"
    assert cells[0].para_index is None


def test_flag_on_emits_one_unit_per_block_paragraph(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")
    cells = _cells("<p>P0</p><p>P1</p><p>P2</p>")

    assert [(c.para_index, c.text) for c in cells] == [
        (0, "P0"),
        (1, "P1"),
        (2, "P2"),
    ]


def test_flag_on_mixed_block_tags_are_separate_units(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")
    cells = _cells("<div>A</div><p>B</p>")

    assert [(c.para_index, c.text) for c in cells] == [(0, "A"), (1, "B")]


def test_flag_on_inline_only_cell_stays_legacy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")
    cells = _cells("a<br>b")

    assert len(cells) == 1
    assert cells[0].para_index is None
    assert cells[0].text == "a b"


def test_flag_on_stray_inline_prefix_stays_legacy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")
    cells = _cells("intro<p>A</p><p>B</p>")

    assert len(cells) == 1
    assert cells[0].para_index is None
    assert cells[0].text == "intro A B"


def test_flag_on_whitespace_only_block_consumes_its_index(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")
    cells = _cells("<p> </p><p>B</p>")

    # The whitespace group is group 0 and emits nothing, but it still consumes
    # index 0 so ORF's ``_para{p}`` for ``B`` is 1, not 0.
    assert [(c.para_index, c.text) for c in cells] == [(1, "B")]


def test_flag_on_empty_cell_emits_no_unit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_FLAG, "1")

    assert _cells("") == []


def test_end_to_end_resnames_switch_with_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cell_inner = "<p>P0</p><p>P1</p><p>P2</p>"

    monkeypatch.setenv(_FLAG, "1")
    assert _table_resnames(_generate_xliff(cell_inner, tmp_path)) == [
        "table_0_r0_c0_para0",
        "table_0_r0_c0_para1",
        "table_0_r0_c0_para2",
    ]

    monkeypatch.delenv(_FLAG, raising=False)
    assert _table_resnames(_generate_xliff(cell_inner, tmp_path)) == ["table_0_r0_c0"]


def test_group_model_agrees_with_orf_html_writer():
    writer = pytest.importorskip("orf.channels.xliff2html.writer")
    soup_cls = pytest.importorskip("bs4").BeautifulSoup
    lxml_html = pytest.importorskip("lxml.html")

    assert _TABLE_CELL_BLOCK_TAGS == writer._HTML_BLOCK_TAGS

    fixtures = [
        "<p>P0</p><p>P1</p><p>P2</p>",
        "<div>A</div><p>B</p>",
        "a<br>b",
        "intro<p>A</p><p>B</p>",
        "<p> </p><p>B</p>",
        "\n<p>A</p>\n<p>B</p>\n",
        "<ul><li>x</li></ul><p>B</p>",
        "<p>A</p><br><p>B</p>",
        "",
    ]
    for inner in fixtures:
        full = _wrap(inner)
        our_cell = soup_cls(full, "html.parser").find("td")
        our_groups = _table_cell_paragraph_groups(our_cell)
        orf_cell = next(iter(lxml_html.fromstring(full).iter("td")))
        orf_groups = writer._cell_paragraph_groups(orf_cell)

        assert len(our_groups) == len(orf_groups), inner
        assert [
            len(g) == 1 and _is_table_cell_block(g[0]) for g in our_groups
        ] == [
            len(g) == 1 and g[0].is_block for g in orf_groups
        ], inner
