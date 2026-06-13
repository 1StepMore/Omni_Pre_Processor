from pptx import Presentation
from pptx.dml.color import RGBColor
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

    def _create_shape_with_font(self, prs, text, font_name=None, font_size=None, color_rgb=None):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        txBox = slide.shapes.add_textbox(Pt(100), Pt(100), Pt(300), Pt(50))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = text
        if font_name is not None:
            run.font.name = font_name
        if font_size is not None:
            run.font.size = font_size
        if color_rgb is not None:
            run.font.color.rgb = color_rgb
        return slide.shapes[-1]

    def test_extract_runs_font_name(self):
        """L1-10 TDD RED: PPTX run.font.name must be extracted into RunData.font_name."""
        prs = Presentation()
        shape = self._create_shape_with_font(prs, "Arial Text", font_name="Arial")
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)

        assert len(runs) == 1
        assert runs[0].font_name == "Arial", (
            f"L1-10 bug: expected font_name='Arial', got {runs[0].font_name!r}"
        )

    def test_extract_runs_font_size(self):
        """L1-11 TDD RED: PPTX run.font.size must be extracted as half-points."""
        prs = Presentation()
        shape = self._create_shape_with_font(prs, "Twelve Pt", font_size=Pt(12))
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)

        assert len(runs) == 1
        assert runs[0].font_size == 24, (
            f"L1-11 bug: expected font_size=24 half-points (12pt), got {runs[0].font_size!r}"
        )

    def test_extract_runs_font_color(self):
        """L1-11 TDD RED: PPTX run.font.color.rgb must be extracted as hex string."""
        prs = Presentation()
        shape = self._create_shape_with_font(
            prs, "Red Text", color_rgb=RGBColor(0xFF, 0x00, 0x00)
        )
        extractor = PPTXExtractor()
        runs = extractor.extract_runs(shape)

        assert len(runs) == 1
        assert runs[0].color == "FF0000", (
            f"L1-11 bug: expected color='FF0000', got {runs[0].color!r}"
        )