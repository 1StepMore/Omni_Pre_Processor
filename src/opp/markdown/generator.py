from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData


class MarkdownGenerator:
    def generate(self, result: ExtractionResult, images_dir: Optional[Path] = None, stem: Optional[str] = None) -> str:
        output_lines = []
        list_buffer: List[str] = []
        list_type = None

        para_images: dict = defaultdict(list)
        for img in result.images:
            key = (
                img.paragraph_index
                if img.paragraph_index is not None
                else img.page_number
                if img.page_number is not None
                else img.slide_index
                if img.slide_index is not None
                else img.element_index
                if img.element_index is not None
                else img.spine_index
            )
            if key is not None:
                img._seq = len(para_images[key]) + 1
                para_images[key].append(img)

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
                ext = self._mime_to_ext(img.mime_type)
                if images_dir is not None:
                    img_filename = f"{stem}_image_{img._seq}.{ext}" if stem else f"image_{img._seq}.{ext}"
                    img_path = images_dir / img_filename
                    img_path.write_bytes(img.data)
                    rel_path = f"./{stem}_images/{img_filename}" if stem else f"./images/{img_filename}"
                    output_lines.append(f"![Image {img._seq}]({rel_path})")
                else:
                    import base64
                    data_uri = f"data:{img.mime_type};base64,{base64.b64encode(img.data).decode('utf-8')}"
                    output_lines.append(f"![Image {img._seq}]({data_uri})")

        flush_list()
        tables = self.generate_tables_md(result.tables)
        if tables:
            output_lines.append("")
            output_lines.append(tables)

        orphaned = [
            img for img in result.images
            if all(f is None for f in (
                img.paragraph_index, img.page_number, img.slide_index,
                img.element_index, img.spine_index
            ))
        ]
        if orphaned:
            output_lines.append(self._generate_images_section(orphaned, images_dir=images_dir, stem=stem))

        return "\n".join(output_lines)

    def generate_to_file(self, result: ExtractionResult, output_path: Path, _attachment_results=None) -> None:
        """Generate markdown output and write to a file.

        Image files are referenced in the markdown using the pattern
        ``![alt]({stem}_image_{seq}.{ext})``, where:

        - ``{stem}`` is derived from the output markdown filename
          (e.g., ``report`` from ``report.md``)
        - ``{seq}`` is a sequential number assigned per paragraph
          (``_image_1``, ``_image_2``, etc.)
        - ``{ext}`` is the appropriate file extension for the image MIME type

        Images are written to a sibling directory named ``{stem}_images/``
        adjacent to the output markdown file.

        Args:
            result: The extraction result containing paragraphs, images, etc.
            output_path: Path for the output markdown file.
            _attachment_results: Optional attachment results (unused).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        images_dir = output_path.parent / f"{output_path.stem}_images"
        images_dir.mkdir(parents=True, exist_ok=True)
        content = self.generate(result, images_dir=images_dir, stem=output_path.stem)
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

    def _generate_images_section(
        self,
        images: List[ImageData],
        images_dir: Optional[Path] = None,
        stem: Optional[str] = None,
    ) -> str:
        lines = ["", "## Images", ""]
        for i, img in enumerate(images):
            if images_dir is not None:
                ext = self._mime_to_ext(img.mime_type)
                img_filename = f"{stem}_image_{i+1}.{ext}" if stem else f"image_{i+1}.{ext}"
                img_path = images_dir / img_filename
                img_path.write_bytes(img.data)
                rel_path = f"./{stem}_images/{img_filename}" if stem else f"./images/{img_filename}"
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