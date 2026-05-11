from pathlib import Path
import json
import pytest

from opp.extractors.ipynb import IPYNBExtractor


class TestIPYNBExtractor:
    def test_supported_extensions(self):
        extractor = IPYNBExtractor()
        extensions = extractor.supported_extensions()
        assert ".ipynb" in extensions

    def test_extract_markdown_cells(self, tmp_path: Path):
        ipynb_path = tmp_path / "test.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "# Hello World\n\nThis is a markdown cell."
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "## Section 2"
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        assert len(result.paragraphs) >= 2
        markdown_paragraphs = [p for p in result.paragraphs if p.style == "Markdown"]
        assert len(markdown_paragraphs) >= 2

    def test_extract_code_cells(self, tmp_path: Path):
        ipynb_path = tmp_path / "code_test.ipynb"
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
                },
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": "x = 1 + 2",
                    "outputs": [],
                    "execution_count": None
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        code_paragraphs = [p for p in result.paragraphs if p.style == "Code"]
        assert len(code_paragraphs) >= 2

    def test_extract_code_cells_with_outputs(self, tmp_path: Path):
        ipynb_path = tmp_path / "output_test.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": "result = 2 + 2",
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": "4\n"
                        }
                    ],
                    "execution_count": 1
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        code_paragraphs = [p for p in result.paragraphs if p.style == "Code"]
        assert len(code_paragraphs) >= 1
        assert "4" in code_paragraphs[0].text

    def test_raw_cells_filtered(self, tmp_path: Path):
        ipynb_path = tmp_path / "raw_filter_test.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "raw",
                    "metadata": {},
                    "source": "This is raw content that should be filtered"
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "This should be kept"
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        raw_paragraphs = [p for p in result.paragraphs if "raw content" in p.text]
        assert len(raw_paragraphs) == 0
        markdown_paragraphs = [p for p in result.paragraphs if p.style == "Markdown"]
        assert len(markdown_paragraphs) >= 1

    def test_empty_cell_source(self, tmp_path: Path):
        ipynb_path = tmp_path / "empty_cell.ipynb"
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": "",
                    "outputs": [],
                    "execution_count": None
                }
            ]
        }
        ipynb_path.write_text(json.dumps(notebook))

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None

    def test_corrupted_file(self, tmp_path: Path):
        corrupted_path = tmp_path / "corrupted.ipynb"
        corrupted_path.write_text("This is not valid JSON")

        extractor = IPYNBExtractor()
        from opp.utils.exceptions import CorruptedFileError

        with pytest.raises(CorruptedFileError):
            extractor.extract(corrupted_path)

    def test_unsupported_format(self, tmp_path: Path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("This is a text file")

        extractor = IPYNBExtractor()
        from opp.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            extractor.extract(txt_path)

    def test_nonexistent_file(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent.ipynb"

        extractor = IPYNBExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(nonexistent)

    @pytest.mark.integration
    def test_extract_with_nbformat(self, tmp_path: Path):
        nbformat = pytest.importorskip("nbformat")

        ipynb_path = tmp_path / "integration_test.ipynb"
        notebook = nbformat.v4.new_notebook()
        notebook.cells.append(nbformat.v4.new_markdown_cell("# Test Heading"))
        code_cell = nbformat.v4.new_code_cell("import numpy as np")
        notebook.cells.append(code_cell)
        nbformat.write(notebook, ipynb_path)

        extractor = IPYNBExtractor()
        result = extractor.extract(ipynb_path)

        assert result.paragraphs is not None
        assert len(result.paragraphs) >= 2