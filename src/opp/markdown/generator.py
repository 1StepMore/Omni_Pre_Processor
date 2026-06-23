from collections import defaultdict
from pathlib import Path
from typing import Any

from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData


class MarkdownGenerator:
    def generate(
        self,
        result: ExtractionResult,
        images_dir: Path | None = None,
        stem: str | None = None,
        style_mapping: dict[str, int] | None = None,
    ) -> str:
        output_lines = []
        list_buffer: list[str] = []
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

        written_images: set = set()

        # Interleave paragraphs and tables by shared position (document order)
        merged = []
        for para in result.paragraphs:
            merged.append((para.position, 'para', para))
        for table in result.tables:
            merged.append((table.position, 'table', table))
        merged.sort(key=lambda x: x[0])

        for _pos, kind, data in merged:
            if kind == 'para':
                para = data
                level = para.level
                style = para.style or ""

                # Apply style_mapping for custom heading styles
                if level is None and style_mapping and para.style in style_mapping:
                    level = style_mapping[para.style]

                is_heading = level is not None and level >= 1
                is_number = "Number" in style
                is_bullet = "List" in style

                if is_heading:
                    flush_list()
                    # Ensure blank line before heading for proper markdown parsing
                    if output_lines and output_lines[-1] != "":
                        output_lines.append("")
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
                        if output_lines and output_lines[-1] != "":
                            output_lines.append("")
                        if para.style == "[TextBox]":
                            output_lines.append(f"> {para.text}")
                        elif para.runs:
                            md_text = self._runs_to_markdown(para.runs)
                            output_lines.append(md_text)
                        else:
                            output_lines.append(para.text)

                # Use para_index_in_body for image lookup (matches paragraph_index from extractor)
                img_key = para.para_index_in_body
                for img in para_images.get(img_key, []):
                    written_images.add(id(img))
                    # E2E-75: skip if the extractor already wrote the
                    # ``![...](...)`` ref inline (e.g. HTML via markdownify).
                    if getattr(img, "is_inline_in_md", False):
                        continue
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

            elif kind == 'table':
                flush_list()
                table_md = self.generate_tables_md([data])
                output_lines.append("")
                output_lines.append(table_md)

        flush_list()

        # E2E-11 fix: track max inline _seq to avoid orphaned images reusing same numbers.
        max_inline_seq = max(
            (img._seq for img in result.images if id(img) in written_images),
            default=0
        )

        # Orphaned = images that were never written during paragraph/table iteration
        orphaned = [img for img in result.images if id(img) not in written_images]
        # E2E-15 fix: further filter by content scan — if an orphaned image's
        # _seq was already output inline (≤ max_inline_seq), skip it to avoid
        # Pandoc embedding the same image twice (inline + Images section).
        orphaned = [
            img for img in orphaned
            if not (hasattr(img, '_seq') and img._seq is not None and img._seq <= max_inline_seq)
        ]
        # E2E-75 fix: images whose ``![...](...)`` ref is already in the
        # markdown text (e.g. HTML via markdownify) must not be re-emitted
        # in the ``## Images`` block — pandoc would embed them twice.
        orphaned = [img for img in orphaned if not getattr(img, "is_inline_in_md", False)]
        if orphaned:
            output_lines.append(self._generate_images_section(
                orphaned, images_dir=images_dir, stem=stem, offset=max_inline_seq
            ))

        return "\n".join(output_lines)

    def _runs_to_markdown(self, runs: list) -> str:
        """Convert OOXML runs to markdown with inline formatting."""
        parts = []
        for run in runs:
            text = run.text
            if run.bold:
                text = f"**{text}**"
            if run.italic:
                text = f"*{text}*"
            if run.strike:
                text = f"~~{text}~~"
            parts.append(text)
        return "".join(parts)

    def generate_to_file(
        self,
        result: ExtractionResult,
        output_path: Path,
        _attachment_results: list[Any] | None = None,
        style_mapping: dict[str, int] | None = None,
        embed_images: bool = True,
    ) -> None:
        """Generate markdown output and write to a file.

        Image files are referenced in the markdown using the pattern
        ``![alt]({stem}_image_{seq}.{ext})``, where ``{ext}`` is the
        appropriate file extension for the image MIME type. When
        ``embed_images=True`` (default), images are written to a sibling
        ``{stem}_images/`` directory and referenced as relative file paths.
        When ``embed_images=False``, images are embedded directly as base64
        ``data:`` URIs in the markdown — this makes the MD self-contained
        for downstream piping (e.g. through OL → pandoc) without requiring
        the image directory to be preserved.

        Args:
            result: The extraction result containing paragraphs, tables, and images
            output_path: Path to write the Markdown file to
            _attachment_results: Optional attachment results (unused).
            style_mapping: Optional dict mapping style names to heading levels.
            embed_images: When True (default), write images to disk and
                reference by relative path. When False, embed as base64 data URIs.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if embed_images:
            images_dir = output_path.parent / f"{output_path.stem}_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            content = self.generate(result, images_dir=images_dir, stem=output_path.stem, style_mapping=style_mapping)
        else:
            content = self.generate(result, images_dir=None, stem=output_path.stem, style_mapping=style_mapping)
        output_path.write_text(content, encoding="utf-8")

    def generate_headings(self, paragraphs: list[ParagraphData], style_mapping: dict[str, int] | None = None) -> str:
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

    def generate_lists(self, paragraphs: list[ParagraphData]) -> str:
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

    def generate_tables_md(
        self,
        tables: list[TableData],
        alignment: list[str] | None = None,
        has_header: bool = True,
    ) -> str:
        result_parts = []
        for table in tables:
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
        images: list[ImageData],
        images_dir: Path | None = None,
        stem: str | None = None,
        offset: int = 0,
    ) -> str:
        lines = ["", "## Images", ""]
        for i, img in enumerate(images):
            if images_dir is not None:
                ext = self._mime_to_ext(img.mime_type)
                img_filename = f"{stem}_image_{i+1+offset}.{ext}" if stem else f"image_{i+1+offset}.{ext}"
                img_path = images_dir / img_filename
                img_path.write_bytes(img.data)
                rel_path = f"./{stem}_images/{img_filename}" if stem else f"./images/{img_filename}"
                lines.append(f"![Image {i+1+offset}]({rel_path})")
            else:
                import base64
                ext = self._mime_to_ext(img.mime_type)
                data_uri = f"data:{img.mime_type};base64,{base64.b64encode(img.data).decode('utf-8')}"
                lines.append(f"![Image {i+1+offset}]({data_uri})")
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