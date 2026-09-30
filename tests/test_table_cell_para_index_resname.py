"""OPP#80 Wave 0A: the generator appends ``_para{p}`` iff para_index is set.

The generator keys only on ``TableCellData.para_index`` (never on the env
flag), so ``None`` keeps the legacy bare ``table_{t}_r{r}_c{c}`` resname and an
integer selects the per-paragraph form.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from opp.utils.dataclasses import ExtractionResult, TableCellData
from opp.xliff import XLIFFFileGenerator


def _resnames(cell: TableCellData, tmp_path: Path) -> list[str]:
    result = ExtractionResult(paragraphs=[], tables=[], images=[], table_cells=[cell])
    out_path = tmp_path / "out.xlf"
    XLIFFFileGenerator.from_extraction_result(result, "en", "zh").write_to_file(out_path)
    return [r.decode("utf-8") for r in re.findall(rb'resname="([^"]+)"', out_path.read_bytes())]


@pytest.mark.parametrize(
    ("para_index", "expected_resname"),
    [
        (2, "table_0_r0_c0_para2"),
        (0, "table_0_r0_c0_para0"),
        (None, "table_0_r0_c0"),
    ],
)
def test_resname_depends_only_on_para_index(
    tmp_path: Path, para_index: int | None, expected_resname: str
):
    cell = TableCellData(table_index=0, row=0, col=0, text="P", para_index=para_index)
    assert _resnames(cell, tmp_path) == [expected_resname]
