from pathlib import Path
from typing import Generator
import pytest
import fitz
import io


def createMinimalPNG(width=10, height=10):
    import zlib, struct
    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)
    header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    raw = b'RGB' * width * height
    idat = zlib.compress(raw)
    return header + png_chunk(b'IHDR', ihdr) + png_chunk(b'IDAT', idat) + png_chunk(b'IEND', b'')


@pytest.fixture
def sample_files_normal(tmp_path: Path) -> Generator[Path, None, None]:
    sample_dir = tmp_path / "normal"
    sample_dir.mkdir()

    from docx import Document
    doc = Document()
    doc.add_heading('Heading 1', level=1)
    doc.add_paragraph('Normal paragraph')
    doc.add_paragraph('Another paragraph')
    doc.save(str(sample_dir / "normal.docx"))

    doc_table = Document()
    table = doc_table.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = 'Header1'
    table.rows[0].cells[1].text = 'Header2'
    table.rows[1].cells[0].text = 'Row1Cell1'
    table.rows[1].cells[1].text = 'Row1Cell2'
    table.rows[2].cells[0].text = 'Row2Cell1'
    table.rows[2].cells[1].text = 'Row2Cell2'
    doc_table.save(str(sample_dir / "with_table.docx"))

    doc_img = Document()
    doc_img.add_paragraph('Image test doc')
    doc_img.save(str(sample_dir / "with_image.docx"))

    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for i in range(4):
        shape = slide.shapes.add_textbox(Inches(0.5 + i*0.3), Inches(1 + i*0.3), Inches(2), Inches(0.5))
        shape.text_frame.paragraphs[0].text = f'Text {i+1}'
    prs.save(str(sample_dir / "normal.pptx"))

    prs_notes = Presentation()
    slide_notes = prs_notes.slides.add_slide(prs_notes.slide_layouts[6])
    notes_slide = slide_notes.notes_slide
    notes_tf = notes_slide.notes_text_frame
    notes_tf.text = 'Speaker notes here'
    prs_notes.save(str(sample_dir / "with_notes.pptx"))

    pdf = fitz.open()
    pdf.new_page(width=595, height=842)
    page = pdf[0]
    rect = fitz.Rect(100, 100, 200, 200)
    page.insert_textbox(rect, 'Hello PDF', fontsize=12)
    pdf.save(str(sample_dir / "native_text.pdf"))

    pdf_table = fitz.open()
    pdf_table.new_page(width=595, height=842)
    page_t = pdf_table[0]
    page_t.draw_line(fitz.Point(100, 100), fitz.Point(200, 100), width=1)
    page_t.draw_line(fitz.Point(100, 200), fitz.Point(200, 200), width=1)
    page_t.draw_line(fitz.Point(100, 100), fitz.Point(100, 200), width=1)
    page_t.draw_line(fitz.Point(200, 100), fitz.Point(200, 200), width=1)
    page_t.insert_text(fitz.Point(110, 150), 'Cell1')
    page_t.insert_text(fitz.Point(160, 150), 'Cell2')
    pdf_table.save(str(sample_dir / "wired_table.pdf"))

    pdf_img = fitz.open()
    pdf_img.new_page(width=595, height=842)
    page_i = pdf_img[0]
    png_data = createMinimalPNG(20, 20)
    img_rect = fitz.Rect(100, 100, 200, 200)
    page_i.insert_image(img_rect, stream=png_data)
    pdf_img.save(str(sample_dir / "with_images.pdf"))

    yield sample_dir


@pytest.fixture
def sample_files_edge(tmp_path: Path) -> Generator[Path, None, None]:
    sample_dir = tmp_path / "edge"
    sample_dir.mkdir()

    from docx import Document
    doc_empty = Document()
    doc_empty.save(str(sample_dir / "empty.docx"))

    doc_single = Document()
    doc_single.add_paragraph('Single Paragraph')
    doc_single.save(str(sample_dir / "single_para.docx"))

    doc_nested = Document()
    table1 = doc_nested.add_table(rows=2, cols=2)
    table1.rows[0].cells[0].text = 'T1H1'
    table1.rows[0].cells[1].text = 'T1H2'
    table1.rows[1].cells[0].text = 'T1R1'
    table1.rows[1].cells[1].text = 'T1R2'
    table2 = doc_nested.add_table(rows=2, cols=2)
    table2.rows[0].cells[0].text = 'T2H1'
    table2.rows[0].cells[1].text = 'T2H2'
    table2.rows[1].cells[0].text = 'T2R1'
    table2.rows[1].cells[1].text = 'T2R2'
    doc_nested.save(str(sample_dir / "nested_table.docx"))

    doc_img = Document()
    doc_img.add_paragraph('Single image doc')
    doc_img.save(str(sample_dir / "single_image.docx"))

    from pptx import Presentation
    from pptx.util import Inches

    prs_single = Presentation()
    slide_s = prs_single.slides.add_slide(prs_single.slide_layouts[6])
    shape_s = slide_s.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(0.5))
    shape_s.text_frame.paragraphs[0].text = 'Single Slide'
    prs_single.save(str(sample_dir / "single_slide.pptx"))

    prs_blank = Presentation()
    prs_blank.slides.add_slide(prs_blank.slide_layouts[6])
    prs_blank.save(str(sample_dir / "blank_slide.pptx"))

    prs_textbox = Presentation()
    slide_tb = prs_textbox.slides.add_slide(prs_textbox.slide_layouts[6])
    shape_tb = slide_tb.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(0.5))
    shape_tb.text_frame.paragraphs[0].text = 'Text Box Content'
    prs_textbox.save(str(sample_dir / "textbox.pptx"))

    prs_grouped = Presentation()
    slide_g = prs_grouped.slides.add_slide(prs_grouped.slide_layouts[6])
    shape_g1 = slide_g.shapes.add_textbox(Inches(1), Inches(1), Inches(1), Inches(0.3))
    shape_g1.text_frame.paragraphs[0].text = 'Shape 1'
    shape_g2 = slide_g.shapes.add_textbox(Inches(1), Inches(1.5), Inches(1), Inches(0.3))
    shape_g2.text_frame.paragraphs[0].text = 'Shape 2'
    prs_grouped.save(str(sample_dir / "grouped.pptx"))

    prs_empty_notes = Presentation()
    prs_empty_notes.slides.add_slide(prs_empty_notes.slide_layouts[6])
    prs_empty_notes.save(str(sample_dir / "empty_notes.pptx"))

    prs_long = Presentation()
    prs_long.slides.add_slide(prs_long.slide_layouts[6])
    prs_long.save(str(sample_dir / "long_notes.pptx"))

    prs_smart = Presentation()
    prs_smart.slides.add_slide(prs_smart.slide_layouts[6])
    prs_smart.save(str(sample_dir / "smartart.pptx"))

    pdf_empty = fitz.open()
    pdf_empty.new_page()
    pdf_empty.save(str(sample_dir / "empty.pdf"))

    pdf_multi = fitz.open()
    pdf_multi.new_page(width=595, height=842)
    page_m = pdf_multi[0]
    rect1 = fitz.Rect(50, 100, 280, 300)
    rect2 = fitz.Rect(315, 100, 545, 300)
    page_m.insert_textbox(rect1, 'Col1 Text', fontsize=12)
    page_m.insert_textbox(rect2, 'Col2 Text', fontsize=12)
    pdf_multi.save(str(sample_dir / " multicolum.pdf"))

    pdf_wireless = fitz.open()
    pdf_wireless.new_page(width=595, height=842)
    page_w = pdf_wireless[0]
    page_w.insert_text(fitz.Point(100, 110), 'Col1 Col2')
    page_w.insert_text(fitz.Point(100, 130), 'Val1 Val2')
    pdf_wireless.save(str(sample_dir / "wireless_table.pdf"))

    pdf_pseudo = fitz.open()
    pdf_pseudo.new_page(width=595, height=842)
    pdf_pseudo.save(str(sample_dir / "pseudo_table.pdf"))

    pdf_comp = fitz.open()
    pdf_comp.new_page(width=595, height=842)
    page_c = pdf_comp[0]
    png_data = createMinimalPNG(20, 20)
    img_rect_c = fitz.Rect(100, 100, 200, 200)
    page_c.insert_image(img_rect_c, stream=png_data)
    pdf_comp.save(str(sample_dir / "compressed_images.pdf"))

    yield sample_dir


@pytest.fixture
def sample_files_error(tmp_path: Path) -> Generator[Path, None, None]:
    sample_dir = tmp_path / "error"
    sample_dir.mkdir()

    (sample_dir / "corrupted.docx").write_bytes(b'not a valid docx')
    (sample_dir / "corrupted.pptx").write_bytes(b'not a valid pptx')
    (sample_dir / "corrupted.pdf").write_bytes(b'not a valid pdf')
    (sample_dir / "zero_byte.docx").write_bytes(b'')
    (sample_dir / "zero_byte.pptx").write_bytes(b'')
    (sample_dir / "zero_byte.pdf").write_bytes(b'')

    from docx import Document
    doc_prot = Document()
    doc_prot.add_paragraph('Test')
    doc_prot.save(str(sample_dir / "password.docx"))

    yield sample_dir