from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData


class MarkdownGenerator:
    def generate(self, result: ExtractionResult) -> str:
        output_lines = []
        list_buffer: List[str] = []
        list_type = None

        para_images: dict = defaultdict(list)
        for img in result.images:
            if img.paragraph_index is not None:
                img._seq = len(para_images[img.paragraph_index]) + 1
                para_images[img.paragraph_index].append(img)

        def flush_list():
            nonlocal list_type
            if list_buffer:
                output_lines.append("")
                output_lines.extend(list_buffer)
                list_buffer.clear()
                list_type = None

        for para in result.paragraphs:
            level = para.level
            style = para.style or ""
            is_heading = level is not None and level >= 1
            is_number = "Number" in style
            is_bullet = "List" in style

            if is_heading:
                flush_list()
                if para.chapter:
                    output_lines.append(f"<!-- chapter: {para.chapter} -->")
                heading = "#" * min(level or 1, 6) + " " + para.text
                output_lines.append(heading)
            elif is_number or is_bullet:
                if is_number:
                    marker = "1. "
                else:
                    marker = "- "
                if list_type is None:
                    list_type = "ordered" if is_number else "bullet"
                if list_type != ("ordered" if is_number else "bullet"):
                    flush_list()
                    list_type = "ordered" if is_number else "bullet"
                list_buffer.append(marker + para.text)
            else:
                flush_list()
                if para.text:
                    output_lines.append(para.text)

            for img in para_images.get(para.position, []):
                import base64
                ext = self._mime_to_ext(img.mime_type)
                data_uri = f"data:{img.mime_type};base64,{base64.b64encode(img.data).decode('utf-8')}"
                output_lines.append(f"![Image {img._seq}]({data_uri})")

        flush_list()
        tables = self.generate_tables_md(result.tables)
        if tables:
            output_lines.append("")
            output_lines.append(tables)

        orphaned = [img for img in result.images if img.paragraph_index is None]
        if orphaned:
            output_lines.append(self._generate_images_section(orphaned, output_path=None))

        return "\n".join(output_lines)

    def generate_to_file(self, result: ExtractionResult, output_path: Path, _attachment_results=None) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate(result)
        output_path.write_text(content, encoding="utf-8")

        if result.images:
            images_dir = output_path.parent / f"{output_path.stem}_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for i, img in enumerate(result.images):
                ext = self._mime_to_ext(img.mime_type)
                img_path = images_dir / f"{output_path.stem}_image_{i+1}.{ext}"
                img_path.write_bytes(img.data)

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

    def _generate_images_section(
        self,
        images: List[ImageData],
        output_path: Optional[Path] = None,
    ) -> str:
        lines = ["", "## Images", ""]
        for i, img in enumerate(images):
            if output_path is not None:
                images_dir = output_path.parent / f"{output_path.stem}_images"
                images_dir.mkdir(parents=True, exist_ok=True)
                ext = self._mime_to_ext(img.mime_type)
                img_path = images_dir / f"{output_path.stem}_image_{i+1}.{ext}"
                img_path.write_bytes(img.data)
                rel_path = f"{output_path.stem}_images/{img_path.name}"
                lines.append(f"![Image {i+1}]({rel_path})")
            else:
                import base64
                ext = self._mime_to_ext(img.mime_type)
                data_uri = f"data:{img.mime_type};base64,{base64.b64encode(img.data).decode('utf-8')}"
                lines.append(f"![Image {i+1}]({data_uri})")
        return '\n'.join(lines)

    def _mime_to_ext(self, mime_type: str) -> str:
        mime_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/bmp": "bmp",
            "image/tiff": "tiff",
            "image/svg+xml": "svg",
        }
        return mime_map.get(mime_type, "bin")