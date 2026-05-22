from pptx import Presentation
from pptx.util import Pt
from opp.extractors.pptx import PPTXExtractor
from opp.utils.dataclasses import RunData


class TestPPTXExtractRuns:
    def _create_shape_with_text(self, prs, text, bold=False, italic=False, underline=False):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        txBox = slide.shapes.add_textbox(Pt(100), Pt(100), Pt(300), Pt(50))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = text
        run.font.bold = bold
        run.font.italic = italic
        run.font.underline = underline
        return slide.shapes[-1]

    def test_extract_runs_single_plain(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Hello World")
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Hello World"
        assert runs[0].bold is False
        assert runs[0].italic is False
        assert runs[0].underline is False
        assert runs[0].strike is False

    def test_extract_runs_single_bold(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Bold Text", bold=True)
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Bold Text"
        assert runs[0].bold is True

    def test_extract_runs_single_italic(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Italic Text", italic=True)
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Italic Text"
        assert runs[0].italic is True

    def test_extract_runs_single_underline(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Underlined Text", underline=True)
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Underlined Text"
        assert runs[0].underline is True

    def test_extract_runs_single_strike(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Strikethrough Text")
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Strikethrough Text"
        assert runs[0].strike is False

    def test_extract_runs_combined_formatting(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "Bold Italic", bold=True, italic=True)
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 1
        assert runs[0].text == "Bold Italic"
        assert runs[0].bold is True
        assert runs[0].italic is True

    def test_extract_runs_empty_text(self):
        prs = Presentation()
        shape = self._create_shape_with_text(prs, "")
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 0

    def test_extract_runs_no_text_frame(self):
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        shape = slide.shapes.add_shape(1, Pt(100), Pt(100), Pt(300), Pt(50))
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)
        assert len(runs) == 0