import logging
from pathlib import Path
from typing import List

from opp.extractors.base import ExtractorBase
from opp.transcriber import AudioTranscriber, TranscriptionResult
from opp.utils.dataclasses import DocumentMetadata, ExtractionResult, ParagraphData

logger = logging.getLogger(__name__)

_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class AudioExtractor(ExtractorBase):
    def supported_extensions(self) -> list[str]:
        return [".wav", ".mp3"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)

        warnings = []
        file_size = input_path.stat().st_size

        if file_size > _MAX_FILE_SIZE_BYTES:
            warnings.append(
                f"File size ({file_size / (1024*1024):.1f}MB) exceeds 500MB. "
                "Processing may be slow or fail."
            )
            logger.warning(
                "Large audio file detected: %s (%.1fMB)",
                input_path.name,
                file_size / (1024 * 1024),
            )

        try:
            transcriber = AudioTranscriber()
            transcription_result = transcriber.transcribe(str(input_path))
            return self._map_result(transcription_result, input_path, warnings)
        except ImportError:
            warnings.append(
                "faster-whisper not installed. Cannot transcribe audio. "
                "Install with: pip install faster-whisper"
            )
            logger.warning("Audio transcription unavailable - faster-whisper not installed")
        except Exception as e:
            warnings.append(f"Transcription failed: {str(e)}")
            logger.exception("Audio transcription failed for %s", input_path.name)

        return ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[],
            warnings=warnings,
            metadata=DocumentMetadata(
                file_size=file_size,
                format_type=input_path.suffix.lower()[1:],
            ),
        )

    def _map_result(
        self,
        result: TranscriptionResult,
        input_path: Path,
        warnings: list[str],
    ) -> ExtractionResult:
        paragraphs = [
            ParagraphData(text=result.text, style="Normal", level=0)
        ] if result.text else []

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            warnings=warnings,
            metadata=DocumentMetadata(
                file_size=input_path.stat().st_size,
                format_type=input_path.suffix.lower()[1:],
            ),
            is_transcription=True
        )