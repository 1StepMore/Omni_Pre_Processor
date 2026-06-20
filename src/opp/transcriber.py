"""Audio transcription module using faster-whisper."""

from dataclasses import dataclass, field

try:
    from faster_whisper import WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    _FASTER_WHISPER_AVAILABLE = False


@dataclass
class TranscriptionSegment:
    """Single segment of transcribed audio with timestamps."""
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""
    text: str
    language: str
    segments: list[TranscriptionSegment] = field(default_factory=list)


class AudioTranscriber:
    """Audio transcriber using faster-whisper for speech-to-text.

    This class provides audio transcription capabilities using the faster-whisper
    implementation of OpenAI's Whisper model. It supports GPU acceleration,
    automatic device detection, and caches the model to avoid re-downloading.

    Attributes:
        model_name: The name of the Whisper model to use (default: "tiny").
        device: The device to use for inference ("cuda" or "cpu").
        compute_type: The compute type for quantization.

    Example:
        >>> transcriber = AudioTranscriber()
        >>> result = transcriber.transcribe("audio.mp3")
        >>> print(result.text)
        >>> for segment in result.segments:
        ...     print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
    """

    def __init__(self, model: str = "tiny") -> None:
        """Initialize the audio transcriber.

        Args:
            model: The faster-whisper model size to use. Options include
                "tiny" (39M params), "base" (74M), "small" (244M),
                "medium" (769M), "large-v3" (1550M). Default is "tiny".

        Raises:
            ImportError: If faster-whisper is not installed.
        """
        if not _FASTER_WHISPER_AVAILABLE:
            raise ImportError(
                "faster-whisper is not installed. "
                "Please install it with: pip install faster-whisper"
            )

        self.model_name = model
        self._model: "WhisperModel" | None = None
        self._device: str | None = None
        self._compute_type: str | None = None

    def _get_model(self) -> "WhisperModel":
        """Load and cache the faster-whisper model.

        Uses GPU with float16 if available, otherwise falls back to CPU with int8.

        Returns:
            Loaded WhisperModel instance.
        """
        if self._model is not None:
            return self._model

        if self._detect_gpu():
            self._device = "cuda"
            self._compute_type = "float16"
        else:
            self._device = "cpu"
            self._compute_type = "int8"

        self._model = WhisperModel(
            self.model_name,
            device=self._device,
            compute_type=self._compute_type,
        )

        return self._model

    def _detect_gpu(self) -> bool:
        """Detect if GPU is available for inference.

        Returns:
            True if CUDA GPU is available, False otherwise.
        """
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            TranscriptionResult containing the transcribed text, detected language,
            and list of segments with timestamps.

        Raises:
            ImportError: If faster-whisper is not installed.
            FileNotFoundError: If the audio file does not exist.
        """
        model_instance = self._get_model()

        segments_gen, info = model_instance.transcribe(
            audio_path,
            vad_filter=True,
        )

        segments_list = [
            TranscriptionSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
            )
            for segment in segments_gen
        ]

        full_text = " ".join(seg.text for seg in segments_list)

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            segments=segments_list,
        )