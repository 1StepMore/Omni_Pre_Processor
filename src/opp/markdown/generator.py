from pathlib import Path
from typing import List

from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData


class MarkdownGenerator:
    def generate(self, result: ExtractionResult) -> str:
        parts = []
        headings = self.generate_headings(result.paragraphs)
        if headings:
            parts.append(headings)

        non_structured = []
        for para in result.paragraphs:
            style = para.style or ""
            if "Heading" not in style and "Number" not in style and "List" not in style:
                if para.text:
                    non_structured.append(para.text)
        if non_structured:
            if parts:
                parts.append("")
            parts.append("\n".join(non_structured))

        lists = self.generate_lists(result.paragraphs)
        if lists:
            if parts:
                parts.append("")
            parts.append(lists)
        tables = self.generate_tables_md(result.tables)
        if tables:
            if parts:
                parts.append("")
            parts.append(tables)
        return "\n".join(parts)

    def generate_to_file(self, result: ExtractionResult, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate(result)
        output_path.write_text(content, encoding="utf-8")

    def generate_headings(self, paragraphs: List[ParagraphData], style_mapping=None) -> str:
        result_lines = []
        for para in paragraphs:
            level = para.level
            if style_mapping and para.style in style_mapping:
                level = style_mapping[para.style]
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
        has_deep_nesting = False
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
                has_deep_nesting = True

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

            if level > 10 or has_deep_nesting:
                indent = ""
            else:
                clamped_level = max(1, min(level, 6))
                indent = "  " * (clamped_level - 1)

            result_lines.append(f"{indent}{marker}{para.text}")

        return '\n'.join(result_lines)

    def generate_tables_md(self, tables: List[TableData], alignment=None, has_header=True) -> str:
        result_parts = []
        for table in tables:
            num_cols = len(table.headers)

            header_cells = [self._escape_table_cell(h) for h in table.headers]
            result_parts.append("| " + " | ".join(header_cells) + " |")

            sep_cells = []
            for i, h in enumerate(table.headers):
                w = len(h)
                base_sep = w + 2
                if alignment and i < len(alignment) and alignment[i] == "left":
                    sep_cells.append(":" + "-" * (base_sep - 1))
                elif alignment and i < len(alignment) and alignment[i] == "right":
                    sep_cells.append("-" * (base_sep - 1) + ":")
                elif alignment and i < len(alignment) and alignment[i] == "center":
                    sep_cells.append(":" + "-" * (base_sep - 2) + ":")
                else:
                    sep_cells.append("-" * base_sep)
            result_parts.append("|" + "|".join(sep_cells) + "|")

            for row in table.rows:
                cells = [self._escape_table_cell(c) for c in row]
                result_parts.append("| " + " | ".join(cells) + " |")

            result_parts.append("")

        return '\n'.join(result_parts).rstrip()

    def _escape_table_cell(self, cell: str) -> str:
        return cell.replace('|', '\\|').replace('\n', ' ')