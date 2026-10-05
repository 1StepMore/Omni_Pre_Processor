import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter

from opp.extractors.base import ExtractorBase
from opp.logger import logger
from opp.utils.dataclasses import (
    ExtractionResult,
    ParagraphData,
    TableData,
)
from opp.utils.exceptions import ValidationError

# Archive-root sidecar entry of the XLSX skeleton: maps XLIFF trans-unit ids to
# spreadsheet cells. Schema is documented on ``_build_skeleton_with_map``.
XLIFF_MAP_ENTRY_NAME = "xliff_map.json"
XLIFF_MAP_VERSION = 1

# Manifest ``key_files`` candidates for an XLSX skeleton (DOCX-style fixed list:
# filtered against what the archive really holds).
_XLSX_KEY_FILES = (
    "[Content_Types].xml",
    "xl/workbook.xml",
    "xl/styles.xml",
    "xl/sharedStrings.xml",
)


class XLSXExtractor(ExtractorBase):
    MAX_ROWS_WARNING = 10000

    def supported_extensions(self) -> list[str]:
        return [".xlsx"]

    def extract_tables(self, input_path: Path) -> list[TableData]:
        self.validate_file(input_path)

        try:
            wb = openpyxl.load_workbook(input_path, data_only=True)
        except Exception as e:
            logger.debug("Failed to open XLSX in extract_tables: %s", e)
            if "password" in str(e).lower():
                raise ValidationError(f"文件受密码保护: {input_path}")
            raise ValueError(f"无法打开XLSX文件: {input_path}")

        result: list[TableData] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            headers: list[str] = []
            rows: list[list[str]] = []

            max_row = ws.max_row or 0
            max_col = ws.max_column or 0

            if max_row == 0 or max_col == 0:
                continue

            # Extract headers from first row
            header_row_has_data = False
            for cell in ws[1]:
                val = cell.value
                if val is None:
                    headers.append("")
                elif isinstance(val, (datetime, date)):
                    headers.append(val.isoformat())
                    header_row_has_data = True
                else:
                    headers.append(str(val))
                    header_row_has_data = True

            # Skip sheet if header row has no data
            if not header_row_has_data:
                continue

            # Extract data rows (skip header row)
            for row_idx in range(2, max_row + 1):
                row_values: list[str] = []
                for col_idx in range(1, max_col + 1):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    val = cell.value
                    if val is None:
                        row_values.append("")
                    elif isinstance(val, (datetime, date)):
                        row_values.append(val.isoformat())
                    else:
                        row_values.append(str(val))
                rows.append(row_values)

            if headers or rows:
                result.append(TableData(headers=headers, rows=rows))

        return result

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            wb = openpyxl.load_workbook(input_path, data_only=True)
        except Exception as e:
            logger.debug("Failed to open XLSX in extract: %s", e)
            if "password" in str(e).lower():
                raise ValidationError(f"文件受密码保护: {input_path}")
            raise ValueError(f"无法打开XLSX文件: {input_path}")

        formula_refs = self._formula_cell_refs(input_path, list(wb.sheetnames))

        paragraphs: list[ParagraphData] = []
        sheets_map: dict[str, list[dict[str, Any]]] = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            paragraphs.append(ParagraphData(
                text=f"=== Sheet: {sheet_name} ===",
                style="sheet_header",
            ))

            if ws.max_row > self.MAX_ROWS_WARNING:
                warnings.append(f"工作表 '{sheet_name}' 超过 {self.MAX_ROWS_WARNING} 行")

            non_anchor_refs = self._merged_non_anchor_refs(ws)
            max_col = ws.max_column or 1
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=max_col):
                row_values = []
                cells: list[dict[str, Any]] = []
                for cell in row:
                    val = cell.value
                    if val is None:
                        row_values.append("")
                    elif isinstance(val, (datetime, date)):
                        row_values.append(val.isoformat())
                    else:
                        row_values.append(str(val))
                    cells.append({
                        "ref": cell.coordinate,
                        "translatable": self._is_translatable(
                            cell, sheet_name, formula_refs, non_anchor_refs
                        ),
                    })
                line = " | ".join(row_values).strip()
                if line:
                    paragraphs.append(ParagraphData(
                        text=line,
                        style=None,
                    ))
                    # The XLIFF generator numbers paragraphs 1..N in list order
                    # (generator.py ``id=str(unit_id)``), so the id this row's
                    # trans-unit is about to receive is len(paragraphs) after the
                    # append above. Reading the id off the shared paragraph list
                    # instead of a private counter makes the alignment structural:
                    # XLSX emits no ``table_cells`` and no table-row paragraph
                    # indices, so no trans-unit is ever skipped in between.
                    # Sheet-header paragraphs consume an id but record no row, so
                    # the map's ids have gaps; consumers look up by id, not by
                    # position.
                    sheets_map.setdefault(sheet_name, []).append({
                        "id": len(paragraphs),
                        "row": row[0].row,
                        "cells": cells,
                    })

        if not any(p.style != "sheet_header" for p in paragraphs):
            warnings.append("工作簿为空")

        skeleton: bytes | None = None
        skeleton_files: list[str] | None = None
        if formula_refs is not None:
            skeleton, skeleton_files = self._build_skeleton_with_map(
                input_path,
                {"version": XLIFF_MAP_VERSION, "sheets": sheets_map},
            )

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=metadata,
            warnings=warnings,
            skeleton=skeleton,
            skeleton_files=skeleton_files,
        )

    @staticmethod
    def _formula_cell_refs(
        input_path: Path, sheet_names: list[str]
    ) -> set[tuple[str, str]] | None:
        """Inventory every formula cell as ``(sheet_name, "A1")``.

        The main workbook is loaded with ``data_only=True``, so a formula cell
        reports its cached value (or ``None`` when the writer stored none) and
        the formula itself is gone — yet writing a translation back into such a
        cell would replace the formula. The formulas therefore come from a second
        ``read_only`` load, which streams instead of building a second cell tree.

        Returns ``None`` when the inventory cannot be built. Callers then produce
        no skeleton at all: a map that silently missed formulas would license
        ORF to overwrite them, which is worse than XLSX staying skeleton-free.
        """
        refs: set[tuple[str, str]] = set()
        formula_wb = None
        try:
            formula_wb = openpyxl.load_workbook(
                input_path, data_only=False, read_only=True
            )
            for name in formula_wb.sheetnames:
                if name not in sheet_names:
                    continue
                for row in formula_wb[name].iter_rows():
                    for cell in row:
                        if cell.data_type == "f":
                            refs.add((name, cell.coordinate))
        except Exception as e:
            logger.warning(
                "XLSX skeleton skipped: cannot inventory formula cells in %s: %s",
                input_path,
                e,
            )
            return None
        finally:
            if formula_wb is not None:
                formula_wb.close()
        return refs

    @staticmethod
    def _merged_non_anchor_refs(ws: Any) -> set[str]:
        """Coordinates inside a merged range that do NOT hold the value."""
        refs: set[str] = set()
        for rng in ws.merged_cells.ranges:
            for row_idx in range(rng.min_row, rng.max_row + 1):
                for col_idx in range(rng.min_col, rng.max_col + 1):
                    if row_idx == rng.min_row and col_idx == rng.min_col:
                        continue
                    refs.add(f"{get_column_letter(col_idx)}{row_idx}")
        return refs

    @staticmethod
    def _is_translatable(
        cell: Any,
        sheet_name: str,
        formula_refs: set[tuple[str, str]] | None,
        non_anchor_refs: set[str],
    ) -> bool:
        """True only for cells whose text may be replaced by a translation.

        False for a formula cell (its text is a cached value), a merged range's
        non-anchor cells (value lives in the top-left anchor), an Excel error
        literal, and anything that is not non-empty text — numbers, dates and
        booleans are data, not prose. ``formula_refs=None`` (inventory failed)
        marks everything non-translatable, keeping the failure fail-closed.
        """
        if formula_refs is None:
            return False
        if cell.coordinate in non_anchor_refs:
            return False
        if (sheet_name, cell.coordinate) in formula_refs:
            return False
        if getattr(cell, "data_type", None) == "e":
            return False
        return isinstance(cell.value, str) and cell.value.strip() != ""

    def _build_skeleton_with_map(
        self, input_path: Path, xliff_map: dict[str, Any]
    ) -> tuple[bytes | None, list[str] | None]:
        """Package the original .xlsx plus the ``xliff_map.json`` sidecar.

        Every original entry is copied with its own ``ZipInfo`` and its raw
        bytes, so ``xl/*.xml`` stays byte-identical and Excel safety holds by
        construction — no attribute is injected into SpreadsheetML, which Excel
        would reject as unreadable content. This deliberately differs from the
        EPUB/HTML skeletons, whose containers are documents that accept an
        injected attribute. The map is an undeclared part at the archive root:
        ORF reads it out of the skeleton, and a consumer that ignores unknown
        parts (Excel included) sees the untouched workbook.

        ``xliff_map`` schema (version 1), consumed by ORF's XLSX backfill::

            {"version": 1,
             "sheets": {"<sheet name>": [
                {"id": <XLIFF trans-unit id>,
                 "row": <1-based spreadsheet row>,
                 "cells": [{"ref": "A1", "translatable": true}, ...]}
             ]}}

        ``cells`` lists every cell the row text was built from, in column order,
        blanks included, so a consumer addresses a cell by its exact ``ref`` and
        writes only where ``translatable`` is true. Do NOT index cells by
        position: the row's ``<source>`` is ``" | ".join(cell texts).strip()``, so
        blank edge columns and a cell value containing ``" | "`` both make the
        segment count drift from ``len(cells)``. A row appears only when it
        produced a trans-unit; a fully blank row can still produce one (its text
        degenerates to ``" |  |"``) and then maps to all-false cells.
        ``translatable`` is false for formula cells, merged-range non-anchor
        cells, Excel error literals and every non-text cell.

        Returns ``(skeleton_bytes, key_files)``; either is ``None`` on failure.
        """
        payload = json.dumps(xliff_map, ensure_ascii=False, indent=2).encode("utf-8")
        buf = io.BytesIO()
        try:
            with zipfile.ZipFile(input_path, "r") as z_in:
                names = z_in.namelist()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z_out:
                    for info in z_in.infolist():
                        z_out.writestr(info, z_in.read(info))
                    z_out.writestr(XLIFF_MAP_ENTRY_NAME, payload)
        except Exception as e:
            # A workbook whose entries are partly unreadable (zlib.error from a
            # damaged member, BadZipFile, a missing entry) still extracts, so a
            # skeleton failure must stay non-fatal and degrade to no skeleton —
            # same tolerance as epub.py's skeleton builder.
            logger.warning("Failed to build XLSX skeleton for %s: %s", input_path, e)
            return None, None

        key_files = [f for f in _XLSX_KEY_FILES if f in names]
        key_files += [n for n in names if n.startswith("xl/worksheets/")]
        return buf.getvalue(), key_files
