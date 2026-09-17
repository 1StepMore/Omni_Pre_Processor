from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
import logging

from opp.detector import detect_format, FormatType
from opp.error_handler import ErrorHandler, ErrorContext
from opp.extractors import DOCXExtractor, PPTXExtractor, XLSXExtractor, CSVExtractor, JSONExtractor, XMLExtractor, HTMLExtractor, EPUBExtractor, EmailExtractor, ImageOCRExtractor, AudioExtractor, VideoExtractor, IPYNBExtractor, YouTubeExtractor
from opp.extractors.pdf2html import PDF2HTMLExtractor
from opp.extractors.base import ExtractorBase
from opp.extractors.email import AttachmentHandler
from opp.markdown import MarkdownGenerator
from opp.resource_manager import ResourceManager
from opp.xliff import XLIFFFileGenerator
from opp.utils.dataclasses import ExtractionResult
from opp.utils.images_json import generate_images_json


# Pinned by the T2 regression scenario + OPP tests + suite W3.2; the CLI
# surfaces it on stderr verbatim (STANDARDS.md#exit-codes). Do not reword.
PDF_XLIFF_UNSUPPORTED_MSG = "XLIFF not supported for PDF format"


@dataclass
class ProcessingResult:
    content: str
    format_type: FormatType
    images_stored: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    extraction_result: ExtractionResult | None = None
    attachment_results: list["ProcessingResult"] = field(default_factory=list)


@dataclass
class BatchResult:
    successful: int
    failed: int
    total_duration_ms: float
    results: list[ProcessingResult] = field(default_factory=list)


@dataclass
class GenerationResult:
    md_path: Path | None = None
    xliff_path: Path | None = None
    errors: list[str] = field(default_factory=list)


class OPPPipeline:
    def __init__(self, resource_storage_dir: Path, config_path: Path | None = None, max_file_size_mb: int = 100) -> None:
        from opp.config import load_config
        load_config(config_path)

        self.resource_storage_dir = Path(resource_storage_dir)
        self.config_path = config_path
        self.resource_manager = ResourceManager(self.resource_storage_dir)
        self.error_handler = ErrorHandler()
        self.max_file_size_mb = max_file_size_mb
        self.logger = logging.getLogger(__name__)
        self.extractors: dict[FormatType, ExtractorBase] = {
            FormatType.DOCX: DOCXExtractor(),
            FormatType.PPTX: PPTXExtractor(),
            FormatType.PDF: PDF2HTMLExtractor(),
            FormatType.XLSX: XLSXExtractor(),
            FormatType.CSV: CSVExtractor(),
            FormatType.JSON: JSONExtractor(),
            FormatType.XML: XMLExtractor(),
            FormatType.HTML: HTMLExtractor(),
            FormatType.EPUB: EPUBExtractor(),
            FormatType.EMAIL: EmailExtractor(),
            FormatType.IMAGE: ImageOCRExtractor(),
            FormatType.AUDIO: AudioExtractor(),
            FormatType.VIDEO: VideoExtractor(),
            FormatType.IPYNB: IPYNBExtractor(),
            FormatType.YOUTUBE: YouTubeExtractor(),
        }
        self.markdown_generator = MarkdownGenerator()

    def generate_markdown(
        self,
        result: ExtractionResult,
        output_path: Path,
        _attachment_results: list["ProcessingResult"] | None = None,
        style_mapping: dict[str, int] | None = None,
        embed_images: bool = True,
    ) -> Path:
        """Generate Markdown file from extraction result.

        Args:
            result: The extraction result containing paragraphs, tables, and images
            output_path: Path to write the Markdown file to
            attachment_results: Optional list of attachment processing results (unused but kept for API compatibility)
            style_mapping: Optional dict mapping style names to heading levels
            embed_images: When True (default), images as separate files.
                When False, embed as base64 data URIs in the markdown.

        Returns:
            The output_path that was written to
        """
        # Issue #50: accept both str and Path (idempotent — Path() of Path is the same)
        output_path = Path(output_path)
        self.markdown_generator.generate_to_file(
            result, output_path, style_mapping=style_mapping, embed_images=embed_images,
        )
        return output_path

    def generate_xliff(
        self,
        result: ExtractionResult,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        request_id: str | None = None,
    ) -> Path:
        """Generate XLIFF file from extraction result.

        Args:
            result: The extraction result containing paragraphs
            output_path: Path to write the XLIFF file to
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'fr')
            request_id: Optional UUID for end-to-end tracing (B2).

        Returns:
            Path to the generated XLIFF file

        Raises:
            ValueError: If the source format is PDF (XLIFF not supported for PDF)
        """
        # Issue #50: accept both str and Path (idempotent — Path() of Path is the same)
        output_path = Path(output_path)
        if result.metadata and result.metadata.format_type == FormatType.PDF.value:
            error_msg = PDF_XLIFF_UNSUPPORTED_MSG
            self.error_handler.add_error(
                ErrorContext(
                    file_path=str(output_path),
                    error_type="UnsupportedFormat",
                    timestamp=datetime.now(),
                    details=error_msg,
                )
            )
            raise ValueError(error_msg)

        generator = XLIFFFileGenerator.from_extraction_result(
            result, source_lang, target_lang, request_id=request_id
        )
        generator.write_to_file(output_path)
        return output_path

    def generate_images_json(
        self,
        result: ExtractionResult,
        output_path: Path,
    ) -> Path:
        """Generate images JSON file from extraction result.

        Args:
            result: The extraction result containing image information
            output_path: Path to write the JSON file to

        Returns:
            The output_path that was written to
        """
        # Issue #50: accept both str and Path (idempotent — Path() of Path is the same)
        output_path = Path(output_path)
        generate_images_json(result, output_path)
        return output_path

    def save_skeleton(
        self,
        result: ExtractionResult,
        base_name: str,
        output_dir: Path,
    ) -> Path | None:
        """Save skeleton ZIP file.

        Args:
            result: ExtractionResult containing skeleton bytes
            base_name: Output file base name
            output_dir: Output directory

        Returns:
            Path to skeleton file, or None if no skeleton
        """
        # Issue #50: accept both str and Path (idempotent — Path() of Path is the same)
        output_dir = Path(output_dir)
        if not result or not result.skeleton:
            return None

        skeleton_path = output_dir / f"{base_name}.skeleton.zip"

        try:
            with open(skeleton_path, "wb") as f:
                f.write(result.skeleton)
            self.logger.info(f"Skeleton saved: {skeleton_path}")
            return skeleton_path
        except IOError as e:
            self.logger.warning(f"Failed to save skeleton: {e}")
            return None

    def process_file(self, file_path: Path) -> ProcessingResult:
        """Process a single file through the full extraction pipeline.

        Args:
            file_path: Path to the file to process.

        Returns:
            ProcessingResult containing content, metadata, resources, and any errors/warnings.
        """
        start_time = datetime.now()
        file_path = Path(file_path)

        if self.max_file_size_mb is not None and self.max_file_size_mb > 0:
            try:
                size_bytes = file_path.stat().st_size
            except (FileNotFoundError, OSError):
                pass
            else:
                limit_bytes = self.max_file_size_mb * 1024 * 1024
                if size_bytes > limit_bytes:
                    raise ValueError(
                        f"File size ({size_bytes} bytes) exceeds limit of {limit_bytes} bytes"
                    )

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
        errors: list[str] = []
        warnings: list[str] = []
        images_stored = 0

        try:
            result: ExtractionResult = extractor.extract(file_path)

            # Belt-and-suspenders for the PDF→XLIFF guard: the DETECTED
            # input format is authoritative. PDF2HTMLExtractor returns an
            # HTML-shaped result; force truthful metadata so the guard in
            # generate_xliff fires even if an extractor relabels it.
            if fmt == FormatType.PDF and result.metadata is not None:
                result.metadata = replace(
                    result.metadata, format_type=FormatType.PDF.value
                )

            # Collect warnings from extraction
            warnings.extend(result.warnings)

            # Step 5: Store images via resource manager
            for image in result.images:
                try:
                    if image.temp_path is not None and image.temp_path.exists():
                        # Large image already streamed to disk — use directly
                        self.resource_manager.add_image(image.temp_path)
                        images_stored += 1
                        # Bug #51: read bytes into image.data before unlinking so
                        # downstream generate_images_json() can compute data_base64
                        if not image.data:
                            image.data = image.temp_path.read_bytes()
                        # Clean up temp file and its directory if empty
                        temp_dir = image.temp_path.parent
                        image.temp_path.unlink(missing_ok=True)
                        try:
                            temp_dir.rmdir()
                        except OSError:
                            pass  # dir not empty, leave it
                    elif image.data:
                        # Small image in memory — write to temp for resource manager
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
                    self.logger.debug("Failed to store image: %s", e)
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
            self.logger.debug("Extraction failed: %s", e)
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

        # Process email attachments recursively
        attachment_results: list[ProcessingResult] = []
        if fmt == FormatType.EMAIL and result.attachments:
            att_handler = AttachmentHandler(self, max_depth=3)
            for att in result.attachments:
                att_result = att_handler.process_attachment(att)
                if att_result is not None:
                    attachment_results.append(att_result)

        return ProcessingResult(
            content=result.content,
            # PDF input is processed through the PDF→HTML→MD pipeline, so
            # the ProcessingResult is reported as HTML (historical contract
            # locked by test_pdf_e2e/test_pipeline_pdf2html_integration).
            # Keyed on the DETECTED format so it does not depend on an
            # extractor relabeling metadata.format_type.
            format_type=FormatType.HTML if fmt == FormatType.PDF else fmt,
            images_stored=images_stored,
            errors=errors,
            warnings=warnings,
            duration_ms=duration_ms,
            extraction_result=result,
            attachment_results=attachment_results,
        )

    def process_batch(self, file_paths: list[Path], max_workers: int | None = 4) -> BatchResult:
        """Process multiple files through the pipeline with optional parallel execution.

        Args:
            file_paths: List of file paths to process.
            max_workers: Maximum number of parallel workers. Defaults to 4.
                When <= 1, processes sequentially (same as before for testing).
                When None, lets ThreadPoolExecutor choose the default.

        Returns:
            BatchResult with statistics and individual results.
        """
        start_time = datetime.now()
        results: list[ProcessingResult] = []
        successful = 0
        failed = 0

        def _process_single(file_path: Path) -> ProcessingResult:
            pipeline = OPPPipeline(
                self.resource_storage_dir,
                config_path=self.config_path,
                max_file_size_mb=self.max_file_size_mb,
            )
            return pipeline.process_file(file_path)

        if max_workers is not None and max_workers <= 1:
            for file_path in file_paths:
                try:
                    result = _process_single(file_path)
                    results.append(result)
                    if not result.errors:
                        successful += 1
                    else:
                        failed += 1
                        # Propagate result-level errors to the parent error_handler
                        # so callers using get_error_stats() see batch-level failures.
                        for err_msg in result.errors:
                            self.error_handler.add_error(
                                ErrorContext(
                                    file_path=str(file_path),
                                    error_type="BatchError",
                                    timestamp=datetime.now(),
                                    details=str(err_msg),
                                )
                            )
                except Exception as e:
                    self.logger.debug("Batch processing error (sequential): %s", e)
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
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_single, fp) for fp in file_paths]
                for i, future in enumerate(futures):
                    file_path = file_paths[i]
                    try:
                        result = future.result()
                        results.append(result)
                        if not result.errors:
                            successful += 1
                        else:
                            failed += 1
                            for err_msg in result.errors:
                                self.error_handler.add_error(
                                    ErrorContext(
                                        file_path=str(file_path),
                                        error_type="BatchError",
                                        timestamp=datetime.now(),
                                        details=str(err_msg),
                                    )
                                )
                    except Exception as e:
                        self.logger.debug("Batch processing error (parallel): %s", e)
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

    def get_error_stats(self) -> dict[str, int]:
        """Get error and warning statistics from the error handler.

        Returns:
            Dictionary with 'errors' and 'warnings' counts.
        """
        return self.error_handler.get_stats()
