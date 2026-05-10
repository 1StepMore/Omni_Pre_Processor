import pandas as pd
import pytest

from opp.channels.table_channel import TableChannel


class TestTableChannel:
    """Tests for TableChannel DataFrame to Markdown conversion."""

    @pytest.fixture
    def channel(self):
        return TableChannel()

    def test_basic_table(self, channel):
        """Test conversion of a basic 3-column, 5-row DataFrame."""
        df = pd.DataFrame({
            "A": [1, 2, 3, 4, 5],
            "B": ["x", "y", "z", "w", "v"],
            "C": [True, False, True, False, True],
        })
        result = channel.convert(df)
        lines = result.split("\n")
        assert len(lines) == 7  # header + separator + 5 data rows
        assert lines[0] == "| A | B | C |"
        assert lines[1] == "| --- | --- | --- |"
        assert "| 1 | x | True |" in result
        assert "| 5 | v | True |" in result

    def test_headers(self, channel):
        """Test that column headers are properly rendered."""
        df = pd.DataFrame({"Name": ["Alice"], "Age": [30], "City": ["NYC"]})
        result = channel.convert(df)
        assert result.startswith("| Name | Age | City |")

    def test_alignment_row(self, channel):
        """Test that separator row uses --- for alignment."""
        df = pd.DataFrame({"X": [1], "Y": [2]})
        result = channel.convert(df)
        lines = result.split("\n")
        assert lines[1] == "| --- | --- |"

    def test_empty_cells(self, channel):
        """Test handling of empty/NaN cells."""
        df = pd.DataFrame({"A": [1, None, 3], "B": ["x", "", "z"]})
        result = channel.convert(df)
        lines = result.split("\n")
        # Skip header (index 0) and separator (index 1)
        data_rows = [l for l in lines[2:] if l.startswith("|")]
        assert "| 1.0 | x |" in data_rows[0]
        # Row with None in column A and "" in column B
        assert "|  |  |" in data_rows[1]
        assert "| 3.0 | z |" in data_rows[2]

    def test_exceeds_ten_columns(self, channel):
        """Test warning comment for tables with more than 10 columns."""
        df = pd.DataFrame({f"col{i}": [i] for i in range(12)})
        result = channel.convert(df)
        assert result.startswith("<!-- table exceeds 10 columns -->")

    def test_complex_nested_special_characters(self, channel):
        """Test escaping of pipe and newline characters in cells."""
        df = pd.DataFrame({
            "A": ["hello|world", "line1\nline2", "pipe|special||double"],
            "B": ["normal", "escape|here", "end"],
        })
        result = channel.convert(df)
        assert r"hello\|world" in result
        assert r"line1 line2" in result  # newlines replaced with space
        assert r"pipe\|special\|\|double" in result

    def test_five_rows_dataframe(self, channel):
        """Test DataFrame with exactly 5 data rows."""
        df = pd.DataFrame({"X": list(range(5)), "Y": list("abcde")})
        result = channel.convert(df)
        lines = [l for l in result.split("\n") if l.startswith("|") and "---" not in l]
        assert len(lines) == 6  # 1 header + 5 data rows