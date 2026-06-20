"""Video extractor for MP4 audio transcription."""

import logging
import tempfile
from pathlib import Path

from opp.extractors.base import ExtractorBase
from opp.transcriber import AudioTranscriber, TranscriptionResult
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ParagraphData

logger = logging.getLogger(__name__)


class VideoExtractor(ExtractorBase):
    """Extractor for MP4 video files using audio transcription.

    Extracts the audio track from MP4 videos and transcribes speech to text
    using faster-whisper. Handles videos without audio tracks gracefully.

    Example:
        >>> extractor = VideoExtractor()
        >>> result = extractor.extract("video.mp4")
        >>> print(result.content)
    """

    def supported_extensions(self) -> list[str]:
        return [".mp4"]

    def extract(self, input_path: Path) -> ExtractionResult:
        """Extract audio from video and transcribe to text.

        Args:
            input_path: Path to the MP4 video file.

        Returns:
            ExtractionResult containing transcribed paragraphs and warnings.
        """
        self.validate_file(input_path)

        temp_wav_path = None
        try:
            audio_segment = self._extract_audio(input_path)
            
            if audio_segment is None:
                logger.warning(f"No audio track found in video: {input_path}")
                return ExtractionResult(
                    paragraphs=[],
                    tables=[],
                    images=[],
                    warnings=[f"No audio track found in video: {input_path}"],
                    metadata=DocumentMetadata(
                        file_size=input_path.stat().st_size,
                        format_type="video",
                    ),
                )

            temp_wav_path = Path(tempfile.gettempdir()) / f"opp_video_{id(input_path)}.wav"
            audio_segment.export(str(temp_wav_path), format="wav")

            transcriber = AudioTranscriber()
            transcription = transcriber.transcribe(str(temp_wav_path))

            return self._map_transcription_to_result(transcription, input_path)

        except ImportError as e:
            logger.error(f"Missing dependency for video extraction: {e}")
            return ExtractionResult(
                paragraphs=[],
                tables=[],
                images=[],
                warnings=[f"Missing dependency for video extraction: {str(e)}"],
                metadata=DocumentMetadata(
                    file_size=input_path.stat().st_size,
                    format_type="video",
                ),
            )
        except Exception as e:
            logger.warning(f"Video extraction failed for {input_path}: {e}")
            return ExtractionResult(
                paragraphs=[],
                tables=[],
                images=[],
                warnings=[f"Video extraction failed: {str(e)}"],
                metadata=DocumentMetadata(
                    file_size=input_path.stat().st_size,
                    format_type="video",
                ),
            )
        finally:
            if temp_wav_path and temp_wav_path.exists():
                try:
                    temp_wav_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_wav_path}: {e}")

    def _extract_audio(self, video_path: Path):
        """Extract audio track from MP4 video.

        Args:
            video_path: Path to the video file.

        Returns:
            AudioSegment if audio track exists, None otherwise.

        Raises:
            ImportError: If pydub is not installed.
        """
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "pydub is required for video audio extraction. "
                "Install it with: pip install pydub"
            )

        try:
            audio = AudioSegment.from_file(str(video_path), format="mp4")
            
            if len(audio) == 0:
                return None
            
            return audio
        except Exception as e:
            logger.warning(f"Failed to extract audio from {video_path}: {e}")
            return None

    def _map_transcription_to_result(
        self, transcription: TranscriptionResult, input_path: Path
    ) -> ExtractionResult:
        """Map TranscriptionResult to ExtractionResult.

        Args:
            transcription: The transcription result from faster-whisper.
            input_path: Original video file path.

        Returns:
            ExtractionResult with transcribed paragraphs.
        """
        paragraphs = []

        if transcription.segments:
            for segment in transcription.segments:
                paragraphs.append(
                    ParagraphData(
                        text=segment.text,
                        style="Normal",
                        level=0,
                    )
                )
        elif transcription.text:
            paragraphs.append(
                ParagraphData(
                    text=transcription.text,
                    style="Normal",
                    level=0,
                )
            )

        metadata = DocumentMetadata(
            file_size=input_path.stat().st_size,
            format_type="video",
            page_count=None,
        )

        warnings = []
        if not paragraphs:
            warnings.append("No speech detected in video audio")

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            metadata=metadata,
            warnings=warnings,
        )