from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from opp.detector import detect_format, FormatType
from opp.error_handler import ErrorHandler, ErrorContext
from opp.extractors import DOCXExtractor, PDFExtractor, PPTXExtractor, XLSXExtractor, CSVExtractor, JSONExtractor, XMLExtractor, HTMLExtractor, EPUBExtractor
from opp.extractors.base import ExtractorBase
from opp.markdown import MarkdownGenerator
from opp.resource_manager import ResourceManager
from opp.xliff import XLIFFFileGenerator
from opp.utils.dataclasses import ExtractionResult


@dataclass
class ProcessingResult:
    content: str
    format_type: FormatType
    images_stored: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    extraction_result: Optional[ExtractionResult] = None


@dataclass
class BatchResult:
    successful: int
    failed: int
    total_duration_ms: float
    results: List[ProcessingResult] = field(default_factory=list)


@dataclass
class GenerationResult:
    md_path: Optional[Path] = None
    xliff_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


class OPPPipeline:
    def __init__(self, resource_storage_dir: Path) -> None:
        self.resource_storage_dir = Path(resource_storage_dir)
        self.resource_manager = ResourceManager(self.resource_storage_dir)
        self.error_handler = ErrorHandler()
        self.extractors: Dict[FormatType, ExtractorBase] = {
            FormatType.DOCX: DOCXExtractor(),
            FormatType.PPTX: PPTXExtractor(),
            FormatType.PDF: PDFExtractor(),
            FormatType.XLSX: XLSXExtractor(),
            FormatType.CSV: CSVExtractor(),
            FormatType.JSON: JSONExtractor(),
            FormatType.XML: XMLExtractor(),
            FormatType.HTML: HTMLExtractor(),
            FormatType.EPUB: EPUBExtractor(),
        }
        self.markdown_generator = MarkdownGenerator()

    def generate_markdown(self, result: ExtractionResult, output_path: Path) -> Path:
        """Generate Markdown file from extraction result.

        Args:
            result: The extraction result containing paragraphs, tables, and images
            output_path: Path to write the Markdown file to

        Returns:
            The output_path that was written to
        """
        self.markdown_generator.generate_to_file(result, output_path)
        return output_path

    def generate_xliff(
        self,
        result: ExtractionResult,
        output_path: Path,
        source_lang: str,
        target_lang: str,
    ) -> Path:
        """Generate XLIFF file from extraction result.

        Args:
            result: The extraction result containing paragraphs
            output_path: Path to write the XLIFF file to
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'fr')

        Returns:
            Path to the generated XLIFF file

        Raises:
            ValueError: If the source format is PDF (XLIFF not supported for PDF)
        """
        if result.metadata.format_type == "PDF":
            error_msg = "XLIFF not supported for PDF format"
            self.error_handler.add_error(
                ErrorContext(
                    file_path=str(output_path),
                    error_type="UnsupportedFormat",
                    timestamp=datetime.now(),
                    details=error_msg,
                )
            )
            raise ValueError(error_msg)

        generator = XLIFFFileGenerator.from_extraction_result(result, source_lang, target_lang)
        generator.write_to_file(output_path)
        return output_path

    def process_file(self, file_path: Path) -> ProcessingResult:
        """Process a single file through the full extraction pipeline.

        Args:
            file_path: Path to the file to process.

        Returns:
            ProcessingResult containing content, metadata, resources, and any errors/warnings.
        """
        start_time = datetime.now()
        file_path = Path(file_path)

        # Step 1: Detect format
        fmt, confidence = detect_format(file_path)

        # Step 2: If unknown format, add warning and return early
        if fmt == FormatType.UNKNOWN:
            warning_msg = f"Unknown format for file: {file_path}"
            self.error_handler.add_warning(
                ErrorContext(
                    file_path=str(file_path),
                    error_type="UnknownFormat",
                    timestamp=datetime.now(),
                    details=warning_msg,
                )
            )
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return ProcessingResult(
                content="",
                format_type=FormatType.UNKNOWN,
                images_stored=0,
                errors=[],
                warnings=[warning_msg],
                duration_ms=duration_ms,
            )

        # Step 3: Select appropriate extractor
        extractor = self.extractors.get(fmt)
        if extractor is None:
            error_msg = f"No extractor available for format: {fmt.value}"
            self.error_handler.add_error(
                ErrorContext(
                    file_path=str(file_path),
                    error_type="NoExtractor",
                    timestamp=datetime.now(),
                    details=error_msg,
                )
            )
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return ProcessingResult(
                content="",
                format_type=fmt,
                images_stored=0,
                errors=[error_msg],
                warnings=[],
                duration_ms=duration_ms,
            )

        # Step 4: Extract content
        errors: List[str] = []
        warnings: List[str] = []
        images_stored = 0

        try:
            result: ExtractionResult = extractor.extract(file_path)

            # Collect warnings from extraction
            warnings.extend(result.warnings)

            # Step 5: Store images via resource manager
            for image in result.images:
                try:
                    # Create a temporary file for the image data
                    ext = image.mime_type.split("/")[-1] if "/" in image.mime_type else "bin"
                    temp_path = self.resource_storage_dir / f"temp_img_{datetime.now().timestamp()}.{ext}"
                    temp_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(temp_path, "wb") as f:
                        f.write(image.data)
                    self.resource_manager.add_image(temp_path)
                    images_stored += 1
                    # Clean up temp file
                    temp_path.unlink()
                except Exception as e:
                    err_msg = f"Failed to store image: {str(e)}"
                    errors.append(err_msg)
                    self.error_handler.add_error(
                        ErrorContext(
                            file_path=str(file_path),
                            error_type="ResourceError",
                            timestamp=datetime.now(),
                            details=err_msg,
                        )
                    )

            # Add extraction warnings to error handler
            for w in result.warnings:
                self.error_handler.add_warning(
                    ErrorContext(
                        file_path=str(file_path),
                        error_type="ExtractionWarning",
                        timestamp=datetime.now(),
                        details=w,
                    )
                )

        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            errors.append(error_msg)
            self.error_handler.add_error(
                ErrorContext(
                    file_path=str(file_path),
                    error_type="ExtractionError",
                    timestamp=datetime.now(),
                    details=error_msg,
                )
            )
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return ProcessingResult(
                content="",
                format_type=fmt,
                images_stored=images_stored,
                errors=errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return ProcessingResult(
            content=result.content,
            format_type=fmt,
            images_stored=images_stored,
            errors=errors,
            warnings=warnings,
            duration_ms=duration_ms,
            extraction_result=result,
        )

    def process_batch(self, file_paths: List[Path]) -> BatchResult:
        """Process multiple files through the pipeline.

        Args:
            file_paths: List of file paths to process.

        Returns:
            BatchResult with statistics and individual results.
        """
        start_time = datetime.now()
        results: List[ProcessingResult] = []
        successful = 0
        failed = 0

        for file_path in file_paths:
            try:
                result = self.process_file(file_path)
                results.append(result)
                if not result.errors:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                # Graceful error handling - continue on individual file failure
                failed += 1
                error_result = ProcessingResult(
                    content="",
                    format_type=FormatType.UNKNOWN,
                    images_stored=0,
                    errors=[f"Batch processing error: {str(e)}"],
                    warnings=[],
                    duration_ms=0.0,
                )
                results.append(error_result)
                self.error_handler.add_error(
                    ErrorContext(
                        file_path=str(file_path),
                        error_type="BatchError",
                        timestamp=datetime.now(),
                        details=str(e),
                    )
                )

        total_duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return BatchResult(
            successful=successful,
            failed=failed,
            total_duration_ms=total_duration_ms,
            results=results,
        )

    def get_error_stats(self) -> Dict[str, int]:
        """Get error and warning statistics from the error handler.

        Returns:
            Dictionary with 'errors' and 'warnings' counts.
        """
        return self.error_handler.get_stats()
