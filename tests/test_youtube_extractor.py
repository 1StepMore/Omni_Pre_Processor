from pathlib import Path
import pytest

from opp.extractors.youtube import YouTubeExtractor, _is_valid_youtube_url, _extract_url_from_file
from opp.error_handler import ExtractionError


class TestYouTubeExtractor:
    def test_supported_extensions(self):
        extractor = YouTubeExtractor()
        extensions = extractor.supported_extensions()
        assert ".url" in extensions

    def test_is_valid_youtube_url_valid(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=abc123XYZ",
            "https://youtube.com/watch?v=abc123XYZ",
            "https://youtu.be/abc123XYZ",
            "https://www.youtube.com/embed/abc123XYZ",
            "https://www.youtube.com/shorts/abc123XYZ",
            "https://www.youtube.com/live/abc123XYZ",
            "http://www.youtube.com/watch?v=abc123XYZ",
        ]
        for url in valid_urls:
            assert _is_valid_youtube_url(url), f"Should be valid: {url}"

    def test_is_valid_youtube_url_invalid(self):
        invalid_urls = [
            "https://www.google.com/watch?v=abc123XYZ",
            "https://vimeo.com/watch?v=abc123XYZ",
            "https://youtube.com/watch",
            "https://youtube.com/watch?v=",
            "not a url",
            "",
        ]
        for url in invalid_urls:
            assert not _is_valid_youtube_url(url), f"Should be invalid: {url}"

    def test_extract_url_from_file(self, tmp_path: Path):
        url_file = tmp_path / "test.url"
        url_file.write_text("URL=https://www.youtube.com/watch?v=abc123XYZ\n")

        url = _extract_url_from_file(url_file)
        assert url == "https://www.youtube.com/watch?v=abc123XYZ"

    def test_extract_url_from_file_multiple_lines(self, tmp_path: Path):
        url_file = tmp_path / "test.url"
        url_file.write_text("Some other line\nURL=https://youtu.be/xyz789\nAnother line\n")

        url = _extract_url_from_file(url_file)
        assert url == "https://youtu.be/xyz789"

    def test_extract_url_from_file_missing_url(self, tmp_path: Path):
        url_file = tmp_path / "test.url"
        url_file.write_text("Some content without URL line\n")

        with pytest.raises(ExtractionError, match="No URL found"):
            _extract_url_from_file(url_file)

    def test_extract_invalid_url_in_file(self, tmp_path: Path):
        url_file = tmp_path / "test.url"
        url_file.write_text("URL=https://www.google.com/search?q=test\n")

        extractor = YouTubeExtractor()
        with pytest.raises(ExtractionError, match="Invalid YouTube URL"):
            extractor.extract(url_file)

    def test_unsupported_format(self, tmp_path: Path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("This is a text file")

        extractor = YouTubeExtractor()
        from opp.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            extractor.extract(txt_path)

    def test_nonexistent_file(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent.url"

        extractor = YouTubeExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(nonexistent)

    def test_empty_file_no_url(self, tmp_path: Path):
        url_file = tmp_path / "empty.url"
        url_file.write_text("")

        extractor = YouTubeExtractor()
        from opp.utils.exceptions import CorruptedFileError
        with pytest.raises(CorruptedFileError):
            extractor.extract(url_file)

    @pytest.mark.integration
    def test_extract_with_markitdown(self, tmp_path: Path):
        markitdown = pytest.importorskip("markitdown")

        url_file = tmp_path / "test.url"
        url_file.write_text("URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")

        extractor = YouTubeExtractor()
        result = extractor.extract(url_file)

        assert result.paragraphs is not None
        assert result.metadata is not None
        assert result.metadata.format_type == "youtube"

    def test_detect_youtube_url_file(self, tmp_path: Path):
        from opp.detector import detect_format, FormatType

        url_file = tmp_path / "video.url"
        url_file.write_text("URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")

        fmt, confidence = detect_format(url_file)
        assert fmt == FormatType.YOUTUBE
        assert confidence == 1.0

    def test_detect_non_youtube_url_file(self, tmp_path: Path):
        from opp.detector import detect_format, FormatType

        url_file = tmp_path / "generic.url"
        url_file.write_text("URL=https://www.example.com/page\n")

        fmt, _ = detect_format(url_file)
        assert fmt == FormatType.UNKNOWN

    def test_detect_url_file_no_url_line(self, tmp_path: Path):
        from opp.detector import detect_format, FormatType

        url_file = tmp_path / "empty.url"
        url_file.write_text("Some other content\n")

        fmt, _ = detect_format(url_file)
        assert fmt == FormatType.UNKNOWN