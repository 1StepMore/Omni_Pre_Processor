import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn

from opp.extractors.base import ExtractorBase
from opp.logger import logger
from opp.utils.dataclasses import (
    ExtractionResult,
    ImageData,
    ParagraphData,
    RunData,
    SlideData,
    TableCellData,
    TableData,
)
from opp.utils.exceptions import CorruptedFileError, UnsupportedFormatError


@dataclass
class _ExtractionState:
    """Deck-wide mutable state shared while walking a presentation's shapes.

    ``position`` is ONE counter for the whole deck: it is bumped for every
    emitted paragraph and every table so ``MarkdownGenerator`` can interleave
    them in shape order (it sorts merged content by ``position``). If it reset
    per slide, every table would sort after every paragraph.

    ``table_index`` is the deck-wide table counter encoded in the
    ``table_{t}_r{r}_c{c}`` resname and must never reset per slide either.
    """

    position: int = 0
    table_index: int = 0
    tables: list[TableData] = field(default_factory=list)
    table_cells: list[TableCellData] = field(default_factory=list)


class PPTXExtractor(ExtractorBase):
    def supported_extensions(self) -> list[str]:
        return [".pptx"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        metadata = self.get_file_info(input_path)
        warnings: list[str] = []

        try:
            prs = Presentation(str(input_path))
        except Exception:
            logger.debug("Failed to open PPTX: %s", input_path)
            if ".pptm" in str(input_path).lower():
                raise UnsupportedFormatError(f"不支持的PPTX格式（宏已启用）: {input_path}")
            raise CorruptedFileError(f"文件损坏或无法解析: {input_path}")

        state = _ExtractionState()
        slides = self.extract_slides(prs, state)
        images = self.extract_images(prs)

        skeleton_bytes: bytes | None = None
        skeleton_files: list[str] | None = None
        try:
            with open(input_path, 'rb') as f:
                skeleton_bytes = f.read()
            with zipfile.ZipFile(input_path, 'r') as zf:
                skeleton_files = [f for f in zf.namelist() if f.startswith('ppt/')]
        except zipfile.BadZipFile:
            warnings.append("Skeleton extraction failed: not a valid ZIP/PPTX file")
            skeleton_bytes = None
            skeleton_files = None

        all_paragraphs: list[ParagraphData] = []
        for slide_data in slides:
            all_paragraphs.extend(slide_data.shapes)

        if not all_paragraphs:
            warnings.append("演示文稿为空")

        metadata = replace(metadata, page_count=len(prs.slides))

        return ExtractionResult(
            paragraphs=all_paragraphs,
            tables=state.tables,
            images=images,
            metadata=metadata,
            warnings=warnings,
            skeleton=skeleton_bytes,
            skeleton_files=skeleton_files,
            table_cells=state.table_cells,
        )

    def extract_slides(
        self, prs: Presentation, state: _ExtractionState
    ) -> list[SlideData]:
        result: list[SlideData] = []
        for i, slide in enumerate(prs.slides):
            shapes = self.extract_shapes(slide, state)
            notes = self.extract_notes(slide)
            result.append(SlideData(
                index=i,
                shapes=shapes,
                notes=notes,
            ))
        return result

    def _is_title_shape(self, shape: Any) -> bool:
        if not shape.is_placeholder:
            return False
        try:
            return shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
        except (ValueError, AttributeError):
            return False

    def extract_runs(self, shape: Any) -> list[RunData]:
        runs = []
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                text = run.text
                if not text or not text.strip():
                    continue
                font = run.font
                font_size_hp = None
                if font.size is not None:
                    font_size_hp = int(font.size.pt * 2)
                color_hex = None
                if font.color.type is not None and font.color.rgb is not None:
                    color_hex = str(font.color.rgb)
                run_data = RunData(
                    text=text,
                    bold=bool(font.bold) if font.bold else False,
                    italic=bool(font.italic) if font.italic else False,
                    underline=bool(font.underline) if font.underline else False,
                    strike=False,
                    font_size=font_size_hp,
                    font_name=font.name,
                    color=color_hex,
                )
                runs.append(run_data)
        return runs

    def extract_shapes(
        self, slide: Any, state: _ExtractionState
    ) -> list[ParagraphData]:
        result: list[ParagraphData] = []
        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                result.extend(self._flatten_group(shape, state))
            elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
                self._extract_table(shape, state)
            elif shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    result.append(self._paragraph_from_shape(shape, state.position))
                    state.position += 1
        return result

    def _paragraph_from_shape(self, shape: Any, position: int) -> ParagraphData:
        runs = self.extract_runs(shape)
        plain_text = ''.join(r.text for r in runs)
        if self._is_title_shape(shape):
            return ParagraphData(
                text=plain_text,
                style="Heading 1",
                level=1,
                runs=runs,
                position=position,
            )
        return ParagraphData(
            text=plain_text,
            style=shape.shape_type.name if hasattr(shape.shape_type, 'name') else None,
            level=None,
            runs=runs,
            position=position,
        )

    def _flatten_group(
        self, group: Any, state: _ExtractionState
    ) -> list[ParagraphData]:
        result: list[ParagraphData] = []
        for shape in group.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                result.extend(self._flatten_group(shape, state))
            elif shape.has_text_frame:
                # Tables nested in a GroupShape have no text frame and are
                # intentionally skipped here, identically to ORF's writer,
                # which only scans top-level p:spTree graphic frames.
                text = shape.text_frame.text.strip()
                if text:
                    result.append(self._paragraph_from_shape(shape, state.position))
                    state.position += 1
        return result

    def _extract_table(self, shape: Any, state: _ExtractionState) -> None:
        """Extract a top-level table GraphicFrame into ``state``.

        Row/col indices come from the raw ``a:tr``/``a:tc`` direct children
        (``findall`` semantics), NOT python-pptx's grid APIs. In a merged
        region the origin ``a:tc`` stays at its raw position and its spanned
        siblings remain in the raw row, so raw indices are exactly what ORF's
        ``findall`` writer will use. Merged-cell grid expansion / de-dup is
        deliberately not implemented here (issue #80): a spanned cell has
        empty text and therefore contributes no trans-unit.
        """
        table = shape.table
        trs = table._tbl.findall(qn("a:tr"))
        if not trs:
            return

        all_rows: list[list[str]] = []
        for row, tr in enumerate(trs):
            tcs = tr.findall(qn("a:tc"))
            values: list[str] = []
            for col in range(len(tcs)):
                text = self._cell_text(table.rows[row].cells[col])
                values.append(text)
                if text:
                    state.table_cells.append(TableCellData(
                        table_index=state.table_index,
                        row=row,
                        col=col,
                        text=text,
                    ))
            all_rows.append(values)

        headers, rows = all_rows[0], all_rows[1:]
        if not headers and not rows:
            return
        state.tables.append(TableData(
            headers=headers,
            rows=rows,
            position=state.position,
        ))
        state.table_index += 1
        state.position += 1

    def _cell_text(self, cell: Any) -> str:
        """Cell text read paragraph-wise and joined with ``"\\n"``.

        Joining runs instead would drop the paragraph boundary (a
        two-paragraph cell must be ``'alpha\\nbeta'``, not ``'alphabeta'``).
        Mirrors the DOCX ``_extract_table_cells`` contract: each paragraph is
        stripped and empty paragraphs are skipped before the ``"\\n"`` join.
        """
        texts = (para.text.strip() for para in cell.text_frame.paragraphs)
        return "\n".join(t for t in texts if t).strip()

    def extract_notes(self, slide: Any) -> str:
        notes_slide = slide.notes_slide
        if notes_slide and notes_slide.notes_text_frame:
            return notes_slide.notes_text_frame.text.strip()
        return ""

    def extract_images(self, prs: Presentation) -> list[ImageData]:
        result: list[ImageData] = []
        for slide_idx, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if hasattr(shape, "image"):
                    try:
                        image = shape.image
                        result.append(ImageData(
                            data=image.blob,
                            mime_type=image.content_type,
                            width=image.size.width if hasattr(image.size, 'width') else None,
                            height=image.size.height if hasattr(image.size, 'height') else None,
                            slide_index=slide_idx,
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to extract image from PPTX: {e}")
        return result
