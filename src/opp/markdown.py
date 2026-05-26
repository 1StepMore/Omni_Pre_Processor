from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData

if TYPE_CHECKING:
    from opp.pipeline import ProcessingResult


class MarkdownGenerator:
    def generate(self, result: ExtractionResult, attachment_results: Optional[List["ProcessingResult"]] = None) -> str:
        parts = []

        content_stream: List[Tuple[int, str, object]] = []

        for para in result.paragraphs:
            content_stream.append((para.position, 'paragraph', para))

        for table in result.tables:
            content_stream.append((table.position, 'table', table))

        content_stream.sort(key=lambda x: x[0])

        for pos, content_type, content in content_stream:
            if content_type == 'paragraph':
                para = content
                if para.level is not None and para.level >= 1:
                    level = para.level
                    if level > 6:
                        level = 6
                    parts.append('#' * level + ' ' + para.text)
                elif para.style and ("List" in para.style or "Number" in para.style):
                    style = para.style or ""
                    if "Number" in style:
                        marker = "- "
                    else:
                        marker = "- "
                    level = para.level if para.level is not None else 1
                    indent = "  " * max(0, level - 1)
                    parts.append(f"{indent}{marker}{para.text}")
                else:
                    parts.append(para.text)
            elif content_type == 'table':
                table = content
                parts.append(self._format_single_table(table))

        if attachment_results:
            parts.append(self._generate_attachments_section(attachment_results))

        return '\n'.join(parts)

    def generate_to_file(
        self,
        result: ExtractionResult,
        output_path: Path,
        attachment_results: Optional[List["ProcessingResult"]] = None,
    ) -> None:
        content = self.generate(result, attachment_results)
        output_path.write_text(content, encoding='utf-8')

        if result.images:
            images_dir = output_path.parent / f"{output_path.stem}_images"
            images_dir.mkdir(exist_ok=True)
            for i, img in enumerate(result.images):
                img_path = images_dir / f"{output_path.stem}_image_{i+1}.png"
                img_path.write_bytes(img.data)

    def generate_headings(self, paragraphs: List[ParagraphData]) -> str:
        result_lines = []
        for para in paragraphs:
            level = para.level
            if level is None or level < 1:
                continue
            if level > 6:
                level = 6
            heading = '#' * level + ' ' + para.text
            result_lines.append(heading)
        return '\n'.join(result_lines)

    def generate_lists(self, paragraphs: List[ParagraphData]) -> str:
        result_lines = []
        ordered_item_num = 0
        for para in paragraphs:
            style = para.style or ""
            if "Number" in style:
                ordered_item_num += 1
                marker = f"{ordered_item_num}. "
            elif "List" in style:
                marker = "- "
                ordered_item_num = 0
            else:
                continue

            if not para.text:
                continue

            level = para.level if para.level is not None else 1

            if level > 10:
                indent = ""
            else:
                level = max(1, min(level, 6))
                indent = "  " * (level - 1)

            result_lines.append(f"{indent}{marker}{para.text}")

        return '\n'.join(result_lines)

    def generate_tables_md(self, tables: List[TableData]) -> str:
        result_parts = []
        for table in tables:
            num_cols = len(table.headers)
            if num_cols > 10:
                result_parts.append("<!-- table exceeds 10 columns -->")

            header_cells = [self._escape_table_cell(h) for h in table.headers]
            result_parts.append("| " + " | ".join(header_cells) + " |")

            sep_cells = ["---"] * num_cols
            result_parts.append("| " + " | ".join(sep_cells) + " |")

            for row in table.rows:
                cells = [self._escape_table_cell(c) for c in row]
                result_parts.append("| " + " | ".join(cells) + " |")

            result_parts.append("")

        return '\n'.join(result_parts).rstrip()

    def _escape_table_cell(self, cell: str) -> str:
        return cell.replace('|', '\\|').replace('\n', ' ')

    def _format_single_table(self, table: TableData) -> str:
        num_cols = len(table.headers)
        if num_cols > 10:
            return "<!-- table exceeds 10 columns -->"

        lines = []
        header_cells = [self._escape_table_cell(h) for h in table.headers]
        lines.append("| " + " | ".join(header_cells) + " |")

        sep_cells = ["---"] * num_cols
        lines.append("| " + " | ".join(sep_cells) + " |")

        for row in table.rows:
            cells = [self._escape_table_cell(c) for c in row]
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")
        return '\n'.join(lines)

    def _generate_attachments_section(self, attachment_results: List["ProcessingResult"]) -> str:
        if not attachment_results:
            return ""
        lines = ["", "## Attachments", ""]
        for att_result in attachment_results:
            if att_result.content:
                lines.append(f"### {att_result.format_type.value} Attachment")
                lines.append("")
                lines.append(att_result.content)
                lines.append("")
        return '\n'.join(lines)
