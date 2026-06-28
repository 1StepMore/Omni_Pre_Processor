"""Unit tests for VideoExtractor (MP4 audio transcription)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opp.extractors.video import VideoExtractor
from opp.transcriber import TranscriptionResult, TranscriptionSegment
from opp.utils.exceptions import CorruptedFileError, ValidationError


@contextmanager
def _mock_pydub_audio_segment(
    from_file_return: object = None, from_file_side_effect: object = None
):
    """Inject a mock pydub module so VideoExtractor._extract_audio can import it."""
    import sys  # noqa: PLC0415

    mock_pydub = MagicMock()
    mock_pydub.AudioSegment.from_file = MagicMock(
        return_value=from_file_return, side_effect=from_file_side_effect
    )
    sys.modules["pydub"] = mock_pydub
    try:
        yield mock_pydub.AudioSegment
    finally:
        sys.modules.pop("pydub", None)


def _make_audio_segment_mock(length: int = 1):
    """Create a MagicMock that behaves like a pydub AudioSegment."""
    seg = MagicMock()
    seg.__len__ = MagicMock(return_value=length)
    seg.export = MagicMock()
    return seg


class TestVideoExtractor:
    """Tests for VideoExtractor class."""

    def test_supported_extensions(self):
        """supported_extensions() returns ['.mp4']."""
        extractor = VideoExtractor()
        assert extractor.supported_extensions() == [".mp4"]

    def test_extract_success_with_segments(self, tmp_path: Path):
        """Successful extraction with segments produces paragraphs."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock()
        mock_transcription = TranscriptionResult(
            text="Hello world",
            language="en",
            segments=[
                TranscriptionSegment(start=0.0, end=1.0, text="Hello world"),
            ],
        )

        with (
            _mock_pydub_audio_segment(from_file_return=mock_segment),
            patch("opp.extractors.video.AudioTranscriber") as mock_transcriber_cls,
        ):
            mock_transcriber = MagicMock()
            mock_transcriber.transcribe = MagicMock(return_value=mock_transcription)
            mock_transcriber_cls.return_value = mock_transcriber

            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].text == "Hello world"
        assert result.paragraphs[0].style == "Normal"
        assert result.metadata is not None
        assert result.metadata.format_type == "video"
        assert result.metadata.file_size > 0
        assert result.warnings == []

    def test_extract_success_with_text_only(self, tmp_path: Path):
        """When transcription has text but no segments, a single paragraph is created."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock()
        mock_transcription = TranscriptionResult(
            text="Transcribed text without segments",
            language="en",
            segments=[],
        )

        with (
            _mock_pydub_audio_segment(from_file_return=mock_segment),
            patch("opp.extractors.video.AudioTranscriber") as mock_transcriber_cls,
        ):
            mock_transcriber = MagicMock()
            mock_transcriber.transcribe = MagicMock(return_value=mock_transcription)
            mock_transcriber_cls.return_value = mock_transcriber

            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].text == "Transcribed text without segments"

    def test_extract_no_audio_track(self, tmp_path: Path):
        """Video with no audio track returns empty paragraphs and a warning."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        with _mock_pydub_audio_segment(from_file_return=None):
            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1
        assert "No audio track" in result.warnings[0]
        assert result.metadata is not None
        assert result.metadata.format_type == "video"

    def test_extract_no_audio_track_empty_segment(self, tmp_path: Path):
        """Video with zero-length audio segment returns empty paragraphs."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock(length=0)

        with _mock_pydub_audio_segment(from_file_return=mock_segment):
            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1
        assert "No audio track" in result.warnings[0]

    def test_extract_missing_pydub(self, tmp_path: Path):
        """Missing pydub dependency raises ImportError caught by extract()."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        # Do NOT mock pydub — pydub is not installed in the test env,
        # so `from pydub import AudioSegment` inside _extract_audio
        # raises ModuleNotFoundError, which is caught by extract().
        extractor = VideoExtractor()
        result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1
        assert "Missing dependency" in result.warnings[0]

    def test_extract_general_exception(self, tmp_path: Path):
        """A general exception during extraction returns empty with a warning."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        with patch.object(
            VideoExtractor, "_extract_audio", side_effect=ValueError("ffmpeg not found")
        ):
            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1
        assert "Video extraction failed" in result.warnings[0]

    def test_extract_missing_file(self, tmp_path: Path):
        """Nonexistent file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.mp4"
        extractor = VideoExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(missing)

    def test_extract_empty_file(self, tmp_path: Path):
        """Empty file raises CorruptedFileError."""
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        extractor = VideoExtractor()
        with pytest.raises(CorruptedFileError):
            extractor.extract(empty)

    def test_extract_unsupported_format(self, tmp_path: Path):
        """Non-MP4 file raises ValidationError."""
        txt = tmp_path / "test.txt"
        txt.write_text("not a video")
        extractor = VideoExtractor()
        with pytest.raises(ValidationError):
            extractor.extract(txt)

    def test_temp_file_cleanup_on_success(self, tmp_path: Path):
        """Temporary WAV file is removed after successful extraction."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock()
        mock_transcription = TranscriptionResult(
            text="Cleanup test",
            language="en",
            segments=[],
        )

        with (
            _mock_pydub_audio_segment(from_file_return=mock_segment),
            patch("opp.extractors.video.tempfile.gettempdir", return_value=str(tmp_path)),
            patch("opp.extractors.video.AudioTranscriber") as mock_transcriber_cls,
        ):
            mock_transcriber = MagicMock()
            mock_transcriber.transcribe = MagicMock(return_value=mock_transcription)
            mock_transcriber_cls.return_value = mock_transcriber

            extractor = VideoExtractor()
            extractor.extract(video_path)

        temp_wavs = list(tmp_path.glob("opp_video_*.wav"))
        assert len(temp_wavs) == 0

    def test_temp_file_cleanup_on_error(self, tmp_path: Path):
        """Temporary WAV file is cleaned up even when transcription fails."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock()

        with (
            _mock_pydub_audio_segment(from_file_return=mock_segment),
            patch("opp.extractors.video.tempfile.gettempdir", return_value=str(tmp_path)),
            patch("opp.extractors.video.AudioTranscriber") as mock_transcriber_cls,
        ):
            mock_transcriber = MagicMock()
            mock_transcriber.transcribe = MagicMock(
                side_effect=Exception("Transcription failed")
            )
            mock_transcriber_cls.return_value = mock_transcriber

            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1

        temp_wavs = list(tmp_path.glob("opp_video_*.wav"))
        assert len(temp_wavs) == 0

    def test_extract_inherits_base_validate(self, tmp_path: Path):
        """VideoExtractor.validate_file is inherited from ExtractorBase."""
        extractor = VideoExtractor()
        video_path = tmp_path / "valid.mp4"
        video_path.write_bytes(b"fake mp4 bytes")
        assert extractor.validate_file(video_path) is True

    def test_extract_no_speech_detected(self, tmp_path: Path):
        """Video with audio but no speech yields a 'no speech' warning."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        mock_segment = _make_audio_segment_mock()
        mock_transcription = TranscriptionResult(
            text="",
            language="en",
            segments=[],
        )

        with (
            _mock_pydub_audio_segment(from_file_return=mock_segment),
            patch("opp.extractors.video.AudioTranscriber") as mock_transcriber_cls,
        ):
            mock_transcriber = MagicMock()
            mock_transcriber.transcribe = MagicMock(return_value=mock_transcription)
            mock_transcriber_cls.return_value = mock_transcriber

            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert any("No speech" in w for w in result.warnings)

    def test_extract_audio_failure_returns_none(self, tmp_path: Path):
        """When _extract_audio returns None (e.g. ffmpeg missing), a warning is issued."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake mp4 bytes")

        with _mock_pydub_audio_segment(
            from_file_side_effect=Exception("ffmpeg executable not found")
        ):
            extractor = VideoExtractor()
            result = extractor.extract(video_path)

        assert result.paragraphs == []
        assert len(result.warnings) == 1
        assert "No audio track" in result.warnings[0]
