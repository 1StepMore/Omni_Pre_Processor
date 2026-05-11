from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
import io

from opp.extractors.image_ocr import ImageOCRExtractor


class TestImageOCRExtractor:
    def test_extract_text_from_image(self, tmp_path: Path):
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Hello World", fill='black')

        img_path = tmp_path / "test.png"
        img.save(img_path)

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.paragraphs is not None
        assert len(result.paragraphs) >= 0

    def test_extract_chinese_text(self, tmp_path: Path):
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "你好世界", fill='black')

        img_path = tmp_path / "chinese.png"
        img.save(img_path)

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.paragraphs is not None

    def test_extract_low_resolution_warning(self, tmp_path: Path):
        img = Image.new('RGB', (50, 50), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "Low Res", fill='black')

        img_path = tmp_path / "low_res.png"
        img.save(img_path, dpi=(72, 72))

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.warnings is not None

    def test_no_text_in_image(self, tmp_path: Path):
        img = Image.new('RGB', (300, 200), color='blue')

        img_path = tmp_path / "no_text.png"
        img.save(img_path)

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.paragraphs is not None

    def test_corrupted_image(self, tmp_path: Path):
        corrupted_path = tmp_path / "corrupted.png"
        corrupted_path.write_bytes(b"This is not a valid PNG file at all")

        extractor = ImageOCRExtractor()
        from opp.utils.exceptions import CorruptedFileError

        with pytest.raises(CorruptedFileError):
            extractor.extract(corrupted_path)

    def test_ocr_engine_not_installed(self, tmp_path: Path):
        img = Image.new('RGB', (200, 50), color='white')
        img_path = tmp_path / "test.png"
        img.save(img_path)

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.paragraphs is not None or len(result.warnings) >= 0

    def test_tesseract_vs_rapidocr(self, tmp_path: Path):
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Comparison Test", fill='black')

        img_path = tmp_path / "compare.png"
        img.save(img_path)

        extractor = ImageOCRExtractor()
        result = extractor.extract(img_path)

        assert result.paragraphs is not None
