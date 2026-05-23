"""Test IPYNB extractor level assignment for markdown vs code cells."""
from pathlib import Path
import json

from opp.extractors.ipynb import IPYNBExtractor


class TestIPYNBLevel:
    def test_markdown_cell_level_is_one(self, tmp_path: Path):
        """Markdown cells should produce ParagraphData with level=1 for heading generation."""
        ipynb_path = tmp_path / "markdown_level_test.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "# Hello World"
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        assert len(result.paragraphs) == 1
        paragraph = result.paragraphs[0]
        assert paragraph.style == "Markdown"
        assert paragraph.level == 1, f"Expected level=1 for markdown cell, got level={paragraph.level}"

    def test_code_cell_level_is_zero(self, tmp_path: Path):
        """Code cells should produce ParagraphData with level=0 and style='Code'."""
        ipynb_path = tmp_path / "code_level_test.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": "print('Hello')",
                    "outputs": [],
                    "execution_count": None
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        assert len(result.paragraphs) == 1
        paragraph = result.paragraphs[0]
        assert paragraph.style == "Code"
        assert paragraph.level == 0, f"Expected level=0 for code cell, got level={paragraph.level}"