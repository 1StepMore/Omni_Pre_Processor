import zipfile
import time
from pathlib import Path
from typing import Generator
import pytest

from opp.extractors.epub import EPUBExtractor
from opp.utils.exceptions import CorruptedFileError, ValidationError


def create_epub_with_ebooklib(tmp_path: Path, filename: str, chapters: list, images: dict | None = None) -> Path:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(f'test-{filename}')
    book.set_title('Test EPUB')
    book.set_language('en')

    epub_chapters = []
    for i, (title, content) in enumerate(chapters):
        c = epub.EpubHtml(title=title, file_name=f'chapter{i+1}.xhtml', lang='en')
        c.content = content
        book.add_item(c)
        epub_chapters.append(c)

    book.spine = epub_chapters
    book.add_item(epub.EpubNav())

    if images:
        for img_name, img_data in images.items():
            img_item = epub.EpubItem(
                uid=img_name.replace('.', '_'),
                file_name=f'images/{img_name}',
                media_type='image/png' if img_name.endswith('.png') else 'image/jpeg',
                content=img_data
            )
            book.add_item(img_item)

    epub_path = tmp_path / filename
    epub.write_epub(str(epub_path), book)
    return epub_path


def create_minimal_png(width=10, height=10):
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
def epub_samples(tmp_path: Path) -> Generator[dict, None, None]:
    samples = {}

    samples['multichapter.epub'] = create_epub_with_ebooklib(
        tmp_path,
        'multichapter.epub',
        [
            ('Chapter 1', '<html><body><h1>Chapter 1</h1><p>First chapter content.</p></body></html>'),
            ('Chapter 2', '<html><body><h1>Chapter 2</h1><p>Second chapter content.</p></body></html>'),
            ('Chapter 3', '<html><body><h1>Chapter 3</h1><p>Third chapter content.</p></body></html>'),
        ]
    )

    png_data = create_minimal_png(20, 20)
    samples['with_images.epub'] = create_epub_with_ebooklib(
        tmp_path,
        'with_images.epub',
        [
            ('Image Chapter', '<html><body><h1>Image Chapter</h1><p><img src="images/test.png" alt="Test Image"/></p></body></html>'),
        ],
        images={'test.png': png_data}
    )

    samples['with_footnotes.epub'] = create_epub_with_ebooklib(
        tmp_path,
        'with_footnotes.epub',
        [
            ('Footnotes', '''<html><body>
                <p>This is text with a footnote.<a href="#fn1" role="doc-noteref">[1]</a></p>
                <aside id="fn1" role="doc-endnote">This is the footnote content.</aside>
            </body></html>'''),
        ]
    )

    samples['single_page.epub'] = create_epub_with_ebooklib(
        tmp_path,
        'single_page.epub',
        [
            ('Single Page', '<html><body><p>Single page content.</p></body></html>'),
        ]
    )

    png_data2 = create_minimal_png(30, 30)
    samples['no_text.epub'] = create_epub_with_ebooklib(
        tmp_path,
        'no_text.epub',
        [
            ('No Text', '<html><body><img src="images/img1.png"/><img src="images/img2.png"/></body></html>'),
        ],
        images={'img1.png': png_data2, 'img2.png': create_minimal_png(15, 15)}
    )

    corrupt_path = tmp_path / 'corrupt.epub'
    corrupt_path.write_bytes(b'This is not a valid ZIP file at all!')
    samples['corrupt.epub'] = corrupt_path

    missing_opf_path = tmp_path / 'missing_opf.epub'
    with zipfile.ZipFile(missing_opf_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        container = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="nonexistent.opf" media-type="application/oad+xml"/>
    </rootfiles>
</container>'''
        zf.writestr("META-INF/container.xml", container)
    samples['missing_opf.epub'] = missing_opf_path

    yield samples


@pytest.fixture
def large_epub(tmp_path: Path) -> Path:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier('test-large-perf')
    book.set_title('Large EPUB')
    book.set_language('en')

    text_per_chapter = 'x' * (500 * 1024)
    large_text = 'Chapter content. ' + text_per_chapter

    chapters = []
    for i in range(200):
        c = epub.EpubHtml(
            title=f'Chapter {i+1}',
            file_name=f'chapter{i+1}.xhtml',
            lang='en'
        )
        c.content = f'<html><body><h1>Chapter {i+1}</h1><p>{large_text}</p></body></html>'
        book.add_item(c)
        chapters.append(c)

    book.spine = chapters
    book.add_item(epub.EpubNav())

    epub_path = tmp_path / 'large.epub'
    epub.write_epub(str(epub_path), book)

    return epub_path


class TestEPUBExtractor:

    def test_supported_extensions(self):
        extractor = EPUBExtractor()
        assert extractor.supported_extensions() == [".epub"]

    def test_multichapter_order(self, epub_samples):
        """Test that multi-chapter EPUB preserves spine order."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_samples['multichapter.epub'])

        # Each chapter has heading + body = 2 paragraphs, 3 chapters = 6 paragraphs
        assert len(result.paragraphs) == 6

        # Verify content order matches spine order
        # Paragraph order: h1, p, h1, p, h1, p
        heading_texts = [p.text for p in result.paragraphs if p.style == "Heading 1"]
        assert heading_texts == ["Chapter 1", "Chapter 2", "Chapter 3"], "Spine order not preserved"

        body_texts = [p.text for p in result.paragraphs if p.style == "Normal"]
        assert body_texts == ["First chapter content.", "Second chapter content.", "Third chapter content."]

    def test_images_extracted(self, epub_samples):
        """Test that all images are extracted from EPUB."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_samples['with_images.epub'])

        assert hasattr(result, 'images')
        assert len(result.images) >= 1

        # Verify image has valid data
        for img in result.images:
            assert img.data is not None
            assert len(img.data) > 0
            assert img.mime_type.startswith('image/')

    def test_footnotes_preserved(self, epub_samples):
        extractor = EPUBExtractor()
        result = extractor.extract(epub_samples['with_footnotes.epub'])

        assert len(result.paragraphs) >= 1

        content_text = "\n".join(p.text for p in result.paragraphs)
        footnote_marker = "[1]"
        assert footnote_marker in content_text, "Footnote reference should be preserved in output"

    def test_single_page(self, epub_samples):
        """Test graceful handling of single page EPUB."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_samples['single_page.epub'])

        assert len(result.paragraphs) >= 1
        content_text = "\n".join(p.text for p in result.paragraphs)
        assert "Single page content" in content_text

    def test_no_text(self, epub_samples):
        """Test graceful handling of EPUB with only images, no text."""
        extractor = EPUBExtractor()
        result = extractor.extract(epub_samples['no_text.epub'])

        # Should handle gracefully, images should still be extracted
        assert hasattr(result, 'images')
        assert len(result.images) >= 2

        # Warning about empty document is acceptable
        assert "文档为空" in result.warnings or len(result.paragraphs) == 0

    def test_large_file_performance(self, large_epub):
        extractor = EPUBExtractor()

        file_size_mb = 100

        start_time = time.time()
        result = extractor.extract(large_epub)
        elapsed_time = time.time() - start_time

        throughput_mbs = file_size_mb / elapsed_time

        assert len(result.paragraphs) > 0
        assert throughput_mbs >= 5.0, f"Throughput {throughput_mbs:.2f}MB/s is below required 5MB/s"

    def test_corrupt_zip(self, epub_samples):
        """Test error handling for corrupt ZIP file."""
        extractor = EPUBExtractor()
        with pytest.raises((CorruptedFileError, zipfile.BadZipFile)):
            extractor.extract(epub_samples['corrupt.epub'])

    def test_missing_opf(self, epub_samples):
        """Test error handling for missing OPF file."""
        extractor = EPUBExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(epub_samples['missing_opf.epub'])


# ── OPP#39: EPUB skeleton + segment IDs ─────────────────────────


def test_epub_skeleton_bytes(tmp_path: Path):
    """OPP#39: EPUB extract must produce skeleton bytes (raw EPUB ZIP)."""
    epub = create_epub_with_ebooklib(
        tmp_path, "skel_test.epub",
        [("Ch1", "<html><body><p>A</p><p>B</p></body></html>")]
    )
    extractor = EPUBExtractor()
    result = extractor.extract(epub)
    assert result.skeleton is not None, "EPUB extract must set skeleton bytes"
    assert len(result.skeleton) > 0, "Skeleton bytes must not be empty"

    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(result.skeleton)) as z:
        names = z.namelist()
        xhtml_files = [n for n in names if n.endswith(('.xhtml', '.html', '.htm'))]
        assert len(xhtml_files) > 0, "Skeleton ZIP must contain XHTML files"


def test_epub_skeleton_has_segment_ids(tmp_path: Path):
    """OPP#39: Skeleton XHTML must have data-trans-unit-id attributes."""
    epub = create_epub_with_ebooklib(
        tmp_path, "segid_test.epub",
        [("Ch1", "<html><body><p>Hello</p><p>World</p></body></html>")]
    )
    extractor = EPUBExtractor()
    result = extractor.extract(epub)
    assert result.skeleton is not None

    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(result.skeleton)) as z:
        spine_xhtml = [
            n for n in z.namelist()
            if n.endswith(('.xhtml', '.html', '.htm'))
            and 'nav' not in n.lower()
        ]
        assert len(spine_xhtml) > 0, "No spine XHTML files found in skeleton"
        for name in spine_xhtml:
            content = z.read(name).decode('utf-8', errors='replace')
            assert 'data-trans-unit-id=' in content, \
                f"Missing data-trans-unit-id in {name}"


def test_epub_skeleton_segment_ids_sequential(tmp_path: Path):
    """OPP#39: Segment IDs must be sequential (para-0, para-1, ...) across chapters."""
    import re
    epub = create_epub_with_ebooklib(
        tmp_path, "seq_test.epub",
        [
            ("Ch1", "<html><body><p>First</p><p>Second</p></body></html>"),
            ("Ch2", "<html><body><p>Third</p><h1>Fourth</h1></body></html>"),
        ]
    )
    extractor = EPUBExtractor()
    result = extractor.extract(epub)
    assert result.skeleton is not None

    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(result.skeleton)) as z:
        xhtml_names = sorted(n for n in z.namelist() if n.endswith('.xhtml'))
        all_ids: list[str] = []
        for name in xhtml_names:
            content = z.read(name).decode('utf-8')
            ids = re.findall(r'data-trans-unit-id="(\d+)"', content)
            all_ids.extend(ids)

        assert len(all_ids) == 4, f"Expected 4 segment IDs, got {len(all_ids)}: {all_ids}"
        assert all_ids == ["1", "2", "3", "4"], f"IDs not 1-indexed sequential: {all_ids}"


def test_epub_skeleton_preserves_paragraphs(tmp_path: Path):
    """OPP#39: Paragraph text must be preserved in skeleton (no content corruption)."""
    epub = create_epub_with_ebooklib(
        tmp_path, "content_test.epub",
        [("Ch1", "<html><body><p>Preserve this text</p><h1>Heading</h1></body></html>")]
    )
    extractor = EPUBExtractor()
    result = extractor.extract(epub)

    # Paragraphs must be extracted correctly
    assert len(result.paragraphs) >= 2
    texts = [p.text for p in result.paragraphs]
    assert "Preserve this text" in texts
    assert "Heading" in texts


def test_epub_skeleton_multichapter(tmp_path: Path):
    """OPP#39: Multi-chapter EPUB must produce skeleton with segment IDs in each chapter."""
    import re
    epub = create_epub_with_ebooklib(
        tmp_path, "multi_test.epub",
        [
            ("Ch1", "<html><body><p>Chapter1 Para1</p></body></html>"),
            ("Ch2", "<html><body><p>Chapter2 Para1</p><p>Chapter2 Para2</p></body></html>"),
            ("Ch3", "<html><body><h1>Chapter3 Title</h1></body></html>"),
        ]
    )
    extractor = EPUBExtractor()
    result = extractor.extract(epub)
    assert result.skeleton is not None

    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(result.skeleton)) as z:
        xhtml_names = sorted(n for n in z.namelist() if n.endswith('.xhtml'))
        all_ids: list[str] = []
        for name in xhtml_names:
            content = z.read(name).decode('utf-8')
            ids = re.findall(r'data-trans-unit-id="(\d+)"', content)
            all_ids.extend(ids)

        # 1 + 2 + 1 = 4 elements total
        assert len(all_ids) == 4, f"Expected 4 segment IDs, got {len(all_ids)}"
        assert all_ids == ["1", "2", "3", "4"], f"IDs not 1-indexed sequential: {all_ids}"
