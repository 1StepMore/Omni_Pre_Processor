from bs4 import BeautifulSoup
from opp.extractors.html import HTMLExtractor
from opp.utils.dataclasses import RunData


class TestHTMLExtractRuns:
    def _make_soup(self, html):
        return BeautifulSoup(html, 'html.parser')

    def test_extract_runs_bold_strong(self):
        soup = self._make_soup('<strong>Bold</strong>')
        element = soup.find('strong')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Bold"
        assert runs[0].bold is True

    def test_extract_runs_bold_b(self):
        soup = self._make_soup('<b>Bold</b>')
        element = soup.find('b')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Bold"
        assert runs[0].bold is True

    def test_extract_runs_italic_em(self):
        soup = self._make_soup('<em>Italic</em>')
        element = soup.find('em')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Italic"
        assert runs[0].italic is True

    def test_extract_runs_italic_i(self):
        soup = self._make_soup('<i>Italic</i>')
        element = soup.find('i')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Italic"
        assert runs[0].italic is True

    def test_extract_runs_underline(self):
        soup = self._make_soup('<u>Underlined</u>')
        element = soup.find('u')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Underlined"
        assert runs[0].underline is True

    def test_extract_runs_strike_s(self):
        soup = self._make_soup('<s>Strikethrough</s>')
        element = soup.find('s')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Strikethrough"
        assert runs[0].strike is True

    def test_extract_runs_strike_del(self):
        soup = self._make_soup('<del>Deleted</del>')
        element = soup.find('del')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 1
        assert runs[0].text == "Deleted"
        assert runs[0].strike is True

    def test_extract_runs_nested(self):
        soup = self._make_soup('<span><strong>Bold</strong> <em>Italic</em></span>')
        element = soup.find('span')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 2
        assert runs[0].text == "Bold"
        assert runs[0].bold is True
        assert runs[1].text == "Italic"
        assert runs[1].italic is True

    def test_extract_runs_empty_text(self):
        soup = self._make_soup('<span></span>')
        element = soup.find('span')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)
        assert len(runs) == 0

    def test_extract_runs_inline_style_font(self):
        """L1-10 TDD RED: HTML inline style font-family/size/color must populate RunData."""
        soup = self._make_soup(
            '<span style="font-family: Arial; font-size: 12pt; color: #FF0000;">Styled</span>'
        )
        element = soup.find('span')
        extractor = HTMLExtractor()
        runs = extractor.extract_runs(element)

        assert len(runs) >= 1
        run = runs[0]
        assert run.font_name == "Arial", (
            f"L1-10 bug: expected font_name='Arial', got {run.font_name!r}"
        )
        assert run.font_size == 24, (
            f"L1-11 bug: expected font_size=24 half-points (12pt), got {run.font_size!r}"
        )
        assert run.color == "FF0000", (
            f"L1-11 bug: expected color='FF0000', got {run.color!r}"
        )