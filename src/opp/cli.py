import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from opp.detector import FormatType, detect_format
from opp.error_handler import ErrorHandler, ErrorContext
from opp.pipeline import OPPPipeline
from opp.resource_manager import ResourceManager
from opp.logger import logger, setup_logger


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opp",
        description="OPP - Omni Pre-Processor. Extract content from DOCX, PPTX, PDF, HTML, and EPUB files.",
        epilog="""Examples:
  opp file.docx                          Extract from a single file
  opp folder/                            Process folder (batch mode)
  opp --detect-format file.docx          Auto-detect format and extract
  opp --resource-dir ./output file.docx  Extract and save resources to ./output
  opp --target-format md --output-dir ./out file.html   Generate markdown output
  opp --target-format xlf --source-lang en --target-lang fr file.epub  Generate XLIFF
        """
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Input files or folders to process (DOCX, PPTX, PDF, HTML, EPUB)"
    )

    parser.add_argument(
        "--detect-format",
        action="store_true",
        help="Auto-detect file format before processing"
    )

    parser.add_argument(
        "--resource-dir",
        type=Path,
        default=None,
        help="Directory for storing extracted resources (images, etc.)"
    )

    parser.add_argument(
        "--report",
        choices=["html", "text"],
        default=None,
        help="Generate report in specified format (html or text)"
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="Enable batch processing mode"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file for extracted content"
    )

    parser.add_argument(
        "--target-format",
        choices=["md", "xlf", "both"],
        default=None,
        help="Output format for generated files: md (markdown), xlf (XLIFF), both"
    )

    parser.add_argument(
        "--source-lang",
        type=str,
        default="en",
        help="Source language code (default: en)"
    )

    parser.add_argument(
        "--target-lang",
        type=str,
        default=None,
        help="Target language code (required for --target-format=xlf or both)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for generated files"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    return parser


def get_supported_extensions() -> List[str]:
    return ['.docx', '.pptx', '.pdf', '.html', '.epub', '.eml', '.msg', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']


def expand_directories(paths: List[Path]) -> List[Path]:
    files = []
    for path in paths:
        if path.is_dir():
            supported_exts = get_supported_extensions()
            for ext in supported_exts:
                for f in path.rglob(f'*{ext}'):
                    if not f.name.startswith('.'):
                        files.append(f)
        else:
            files.append(path)
    return files


def process_single_file(
    file_path: Path,
    args: argparse.Namespace,
    pipeline: OPPPipeline,
    stats: dict,
    error_handler: ErrorHandler
) -> bool:
    try:
        proc_result = pipeline.process_file(file_path)

        if proc_result.errors:
            stats["errors"] += 1
            for error in proc_result.errors:
                logger.error(f"{file_path}: {error}")
            return False

        if proc_result.extraction_result is None:
            stats["errors"] += 1
            logger.error(f"No extraction result for {file_path}")
            return False

        output_dir = args.output_dir if args.output_dir else file_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = file_path.stem

        if args.target_format in ("md", "both"):
            md_path = output_dir / f"{base_name}.md"
            pipeline.generate_markdown(proc_result.extraction_result, md_path)
            logger.info(f"Generated: {md_path}")

        if args.target_format in ("xlf", "both"):
            xliff_path = output_dir / f"{base_name}.xlf"
            pipeline.generate_xliff(
                proc_result.extraction_result,
                xliff_path,
                args.source_lang,
                args.target_lang
            )
            logger.info(f"Generated: {xliff_path}")

        return True

    except Exception as e:
        stats["errors"] += 1
        logger.error(f"Error processing {file_path}: {e}")
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.target_format in ("xlf", "both") and not args.target_lang:
        parser.error("--target-lang is required when --target-format is 'xlf' or 'both'")

    setup_logger(args.verbose)

    if args.verbose:
        logger.info(f"OPP CLI v0.1.0")
        logger.info(f"Processing {len(args.files)} input(s)")

    start_time = time.time()
    error_handler = ErrorHandler()
    stats = {
        "files_processed": 0,
        "errors": 0,
        "warnings": 0,
        "duration_seconds": 0.0
    }

    all_files = expand_directories(args.files)

    if len(all_files) != len(args.files):
        logger.info(f"Expanded {len(args.files)} input(s) to {len(all_files)} file(s)")

    if not all_files:
        logger.warning("No supported files found")
        return 1

    if len(all_files) > 1 and not args.output_dir:
        args.output_dir = args.files[0].parent / f"{args.files[0].name}_converted"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Batch output directory: {args.output_dir}")

    pipeline = OPPPipeline(resource_storage_dir=args.resource_dir or (Path.cwd() / "resources"))

    for i, file_path in enumerate(all_files, 1):
        if args.verbose:
            logger.info(f"[{i}/{len(all_files)}] Processing: {file_path}")

        detected_format = None
        if args.detect_format:
            fmt, confidence = detect_format(file_path)
            detected_format = fmt.value
            if args.verbose:
                logger.info(f"  Detected: {fmt.value} (confidence: {confidence})")

            if fmt == FormatType.UNKNOWN:
                logger.error(f"Unknown file format: {file_path}")
                error_handler.add_error(ErrorContext(
                    file_path=str(file_path),
                    error_type="detection",
                    timestamp=datetime.now(),
                    details=f"Unknown format, confidence: {confidence}"
                ))
                stats["errors"] += 1
                continue

        if args.target_format:
            success = process_single_file(file_path, args, pipeline, stats, error_handler)
            if success:
                stats["files_processed"] += 1
        else:
            result = {
                "file": str(file_path),
                "success": True,
                "format": detected_format,
                "errors": [],
                "warnings": []
            }
            if result["success"]:
                stats["files_processed"] += 1
            else:
                stats["errors"] += 1

    if args.report:
        if args.report == "html":
            report = error_handler.generate_html_report(file_count=stats["files_processed"])
        else:
            report = error_handler.generate_text_report(file_count=stats["files_processed"])

        if args.output:
            args.output.write_text(report, encoding="utf-8")
            logger.info(f"Report saved to: {args.output}")
        else:
            print("\n" + report)

    duration = time.time() - start_time
    stats["duration_seconds"] = duration

    logger.info(f"Completed: {stats['files_processed']} succeeded, {stats['errors']} failed")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
