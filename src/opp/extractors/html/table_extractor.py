"""HTML-to-Markdown table fixup utilities.

Detects and corrects broken or inconsistent markdown table formatting
produced by markdownify when converting complex HTML tables.
"""


def fix_tables(md_content: str) -> str:
    """Repair broken markdown tables by detecting inconsistent column counts.

    Lines in a table block must have the same number of pipe (``|``)
    delimiters. If they differ (sign of a complex table with ``colspan``
    or ``rowspan``), a comment is inserted so the mismatch is visible.
    """
    lines = md_content.split("\n")
    result = []
    in_table = False
    table_lines = []

    for line in lines:
        if line.startswith("|"):
            table_lines.append(line)
            in_table = True
        else:
            if in_table:
                if _check_table_broken(table_lines):
                    result.append("<!-- complex table: HTML fallback -->")
                    for tl in table_lines:
                        result.append(tl)
                else:
                    result.extend(table_lines)
                table_lines = []
                in_table = False
            result.append(line)

    if in_table:
        if _check_table_broken(table_lines):
            result.append("<!-- complex table: HTML fallback -->")
            result.extend(table_lines)
        else:
            result.extend(table_lines)

    return "\n".join(result)


def _check_table_broken(table_lines: list[str]) -> bool:
    """Check if a table block has inconsistent column counts."""
    if len(table_lines) < 2:
        return False

    pipe_counts = [line.count("|") for line in table_lines]
    if len(set(pipe_counts)) > 1:
        return True

    return False
