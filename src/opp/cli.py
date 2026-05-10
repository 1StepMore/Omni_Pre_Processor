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


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opp",
        description="OPP - Omni Pre-Processor. Extract content from DOCX, PPTX, and PDF files.",
        epilog="""Examples:
  opp file.docx                          Extract from a single file
  opp --detect-format file.docx          Auto-detect format and extract
  opp --resource-dir ./output file.docx  Extract and save resources to ./output
  opp --report html file.docx            Generate HTML report after extraction
  opp --batch file1.docx file2.pdf       Process multiple files
  opp --target-format md --output-dir ./out file.docx   Generate markdown output
  opp --target-format xlf --source-lang en --target-lang fr file.docx  Generate XLIFF
        """
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Input files to process (DOCX, PPTX, PDF)"
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


def detect_and_report_format(file_path: Path) -> FormatType:
    fmt, confidence = detect_format(file_path)
    return fmt


def process_file(
    file_path: Path,
    detect_format_flag: bool = False,
    resource_dir: Optional[Path] = None,
    error_handler: Optional[ErrorHandler] = None
) -> dict:
    result = {
        "file": str(file_path),
        "success": False,
        "format": None,
        "errors": [],
        "warnings": []
    }

    try:
        if detect_format_flag:
            fmt, confidence = detect_format(file_path)
            result["format"] = fmt.value
            result["confidence"] = confidence
            if fmt == FormatType.UNKNOWN:
                result["errors"].append(f"Unknown format (confidence: {confidence})")
                return result

        result["success"] = True

    except FileNotFoundError:
        result["errors"].append(f"File not found: {file_path}")
    except Exception as e:
        result["errors"].append(f"Processing error: {str(e)}")

    return result


def print_statistics(stats: dict) -> None:
    print("\n" + "=" * 50)
    print("PROCESSING STATISTICS")
    print("=" * 50)
    print(f"  Files processed: {stats.get('files_processed', 0)}")
    print(f"  Errors:          {stats.get('errors', 0)}")
    print(f"  Warnings:        {stats.get('warnings', 0)}")
    duration = stats.get('duration_seconds', 0.0)
    print(f"  Duration:        {duration:.2f} seconds")
    if duration > 0:
        rate = stats.get('files_processed', 0) / duration
        print(f"  Throughput:      {rate:.2f} files/second")
    print("=" * 50)


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.target_format in ("xlf", "both") and not args.target_lang:
        parser.error("--target-lang is required when --target-format is 'xlf' or 'both'")

    if args.verbose:
        print(f"OPP CLI v0.1.0")
        print(f"Processing {len(args.files)} file(s)")

    start_time = time.time()
    error_handler = ErrorHandler()
    stats = {
        "files_processed": 0,
        "errors": 0,
        "warnings": 0,
        "duration_seconds": 0.0
    }

    for i, file_path in enumerate(args.files, 1):
        if args.verbose or args.batch:
            print(f"[{i}/{len(args.files)}] Processing: {file_path}")

        detected_format = None
        if args.detect_format:
            fmt, confidence = detect_format(file_path)
            detected_format = fmt.value
            if args.verbose:
                print(f"  Detected: {fmt.value} (confidence: {confidence})")

            if fmt == FormatType.UNKNOWN:
                print(f"  ERROR: Unknown file format")
                error_handler.add_error(ErrorContext(
                    file_path=str(file_path),
                    error_type="detection",
                    timestamp=datetime.now(),
                    details=f"Unknown format, confidence: {confidence}"
                ))
                stats["errors"] += 1
                continue

        result = process_file(
            file_path,
            detect_format_flag=args.detect_format,
            resource_dir=args.resource_dir,
            error_handler=error_handler
        )

        # If target-format is specified, use OPPPipeline for full extraction + generation
        if args.target_format:
            resource_dir = args.resource_dir or (file_path.parent / "resources")
            pipeline = OPPPipeline(resource_storage_dir=resource_dir)

            try:
                proc_result = pipeline.process_file(file_path)

                if proc_result.errors:
                    stats["errors"] += 1
                    for error in proc_result.errors:
                        if args.verbose:
                            print(f"  ERROR: {error}")
                    continue

                if proc_result.extraction_result is None:
                    stats["errors"] += 1
                    if args.verbose:
                        print(f"  ERROR: No extraction result")
                    continue

                # Determine output directory
                output_dir = args.output_dir if args.output_dir else file_path.parent
                output_dir.mkdir(parents=True, exist_ok=True)

                base_name = file_path.stem

                # Generate output based on target-format
                if args.target_format in ("md", "both"):
                    md_path = output_dir / f"{base_name}.md"
                    pipeline.generate_markdown(proc_result.extraction_result, md_path)
                    if args.verbose:
                        print(f"  Generated: {md_path}")

                if args.target_format in ("xlf", "both"):
                    xliff_path = output_dir / f"{base_name}.xlf"
                    pipeline.generate_xliff(
                        proc_result.extraction_result,
                        xliff_path,
                        args.source_lang,
                        args.target_lang
                    )
                    if args.verbose:
                        print(f"  Generated: {xliff_path}")

                stats["files_processed"] += 1
                if args.verbose:
                    print(f"  Success!")

            except Exception as e:
                stats["errors"] += 1
                if args.verbose:
                    print(f"  ERROR: {e}")
            continue

        if result["success"]:
            stats["files_processed"] += 1
            if args.verbose:
                print(f"  Success!")
        else:
            stats["errors"] += 1
            for error in result.get("errors", []):
                if args.verbose:
                    print(f"  ERROR: {error}")

    if args.report:
        if args.verbose:
            print(f"\nGenerating {args.report} report...")

        if args.report == "html":
            report = error_handler.generate_html_report(file_count=stats["files_processed"])
        else:
            report = error_handler.generate_text_report(file_count=stats["files_processed"])

        if args.output:
            args.output.write_text(report, encoding="utf-8")
            if args.verbose:
                print(f"Report saved to: {args.output}")
        else:
            print("\n" + report)

    duration = time.time() - start_time
    stats["duration_seconds"] = duration

    print_statistics(stats)

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())