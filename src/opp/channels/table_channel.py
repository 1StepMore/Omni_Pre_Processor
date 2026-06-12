from typing import List

import pandas as pd


class TableChannel:
    """Converts pandas DataFrame to Markdown table string."""

    def convert(self, df: pd.DataFrame) -> str:
        """Convert a DataFrame to a Markdown table.

        Args:
            df: pandas DataFrame to convert

        Returns:
            Markdown table string
        """
        parts: list[str] = []
        num_cols = len(df.columns)

        if num_cols > 10:
            parts.append("<!-- table exceeds 10 columns -->")

        header_cells = [self._escape_table_cell(str(h)) for h in df.columns]
        parts.append("| " + " | ".join(header_cells) + " |")

        sep_cells = ["---"] * num_cols
        parts.append("| " + " | ".join(sep_cells) + " |")

        for _, row in df.iterrows():
            cells = [self._escape_table_cell(str(val)) if pd.notna(val) else "" for val in row]
            parts.append("| " + " | ".join(cells) + " |")

        return "\n".join(parts)

    def _escape_table_cell(self, cell: str) -> str:
        """Escape special characters in a table cell for Markdown."""
        return cell.replace("|", "\\|").replace("\n", " ")