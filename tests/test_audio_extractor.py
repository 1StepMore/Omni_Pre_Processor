import importlib.util
import struct
import wave
from pathlib import Path

import pytest
from opp.extractors.audio import AudioExtractor


class TestAudioExtractor:
    def test_supported_extensions(self):
        extractor = AudioExtractor()
        extensions = extractor.supported_extensions()
        assert ".wav" in extensions
        assert ".mp3" in extensions

    def test_extract_wav_metadata(self, tmp_path: Path):
        wav_path = tmp_path / "test.wav"
        self._create_wav_file(wav_path, duration_seconds=1)

        extractor = AudioExtractor()
        result = extractor.extract(wav_path)

        assert result.metadata is not None
        assert result.metadata.file_size > 0
        assert result.metadata.format_type == "wav"

    @pytest.mark.skipif(
        importlib.util.find_spec("faster_whisper") is not None,
        reason="only valid when faster-whisper is NOT installed (CI installs it)",
    )
    def test_extract_wav_without_faster_whisper(self, tmp_path: Path):
        wav_path = tmp_path / "test.wav"
        self._create_wav_file(wav_path, duration_seconds=1)

        extractor = AudioExtractor()
        result = extractor.extract(wav_path)

        assert result.warnings is not None
        assert len(result.warnings) >= 1

    def test_extract_empty_wav(self, tmp_path: Path):
        wav_path = tmp_path / "empty.wav"
        wav_path.write_bytes(b"")

        extractor = AudioExtractor()
        from opp.utils.exceptions import CorruptedFileError

        with pytest.raises(CorruptedFileError):
            extractor.extract(wav_path)

    def test_extract_unsupported_format(self, tmp_path: Path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("This is a text file")

        extractor = AudioExtractor()
        from opp.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            extractor.extract(txt_path)

    def test_extract_nonexistent_file(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent.wav"

        extractor = AudioExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(nonexistent)

    def test_large_file_threshold(self):
        from opp.extractors.audio import _MAX_FILE_SIZE_BYTES
        assert _MAX_FILE_SIZE_BYTES == 500 * 1024 * 1024

    @pytest.mark.xfail(reason="Synthetic WAV is not recognizable by faster-whisper; see integration suite for end-to-end audio tests.")
    @pytest.mark.integration
    def test_extract_wav_with_faster_whisper(self, tmp_path: Path):
        pytest.importorskip("faster_whisper")
        pytest.importorskip("torch")

    @staticmethod
    def _create_wav_file(path: Path, duration_seconds: int = 1, sample_rate: int = 16000):
        num_samples = duration_seconds * sample_rate
        with wave.open(str(path), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            import math
            for i in range(num_samples):
                value = int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
                wav_file.writeframes(struct.pack('<h', value))