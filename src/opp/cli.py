"""OPP CLI — Omni Pre-Processor command-line interface.

Entry point: ``opp`` (defined in ``pyproject.toml`` as ``opp.cli:main``).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from opp.detector import FormatType, detect_format
from opp.error_handler import ErrorHandler, ErrorContext
from opp.logger import setup_logger, get_logger
from opp.pipeline import OPPPipeline, ProcessingResult

# ── Backward-compatibility re-exports ──────────────────────────────────
# These are imported from the split modules so that existing tests and
# code continue to work when they do ``from opp.cli import <name>`` or
# ``patch("opp.cli.<name>")``.
from opp.cliutils import (  # noqa: F401
    _cache_root,
    _cache_key,
    _relevant_config_for_cache,
    _check_cache,
    _write_cache,
    _clear_opp_cache,
    _load_env_for_opp,
    _load_dotenv_for_opp,
    get_supported_extensions,
    expand_directories,
    _detect_format_from_extension,
    _compute_file_md5,
    _count_xliff_units,
    get_opp_version,
)
from opp.commands.extract import process_single_file  # noqa: F401
from opp.commands.batch import batch_process  # noqa: F401
from opp.commands.mcp import start_mcp  # noqa: F401


# ========== CLI app definition ==========


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
  opp --ocr-engine tesseract --ocr-lang eng file.png  OCR with Tesseract (English)
  opp --ocr-engine rapidocr file.jpg     OCR with RapidOCR
        """
    )

    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Input files or folders to process (DOCX, PPTX, PDF, HTML, EPUB). Optional when --capabilities is set."
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
        choices=["md", "xlf", "both", "html"],
        default=None,
        help="Output format for generated files: md (markdown), xlf (XLIFF), both, html (PDF→HTML via pandoc)"
    )

    parser.add_argument(
        "--source-lang",
        type=str,
        default="zh",
        help="Source language code (default: zh — the project's primary translation direction)"
    )

    parser.add_argument(
        "--target-lang",
        type=str,
        default=None,
        help="Target language code (required when --target-format is xlf or both). "
             "Falls back to 'en' for md-only extraction."
    )

    parser.add_argument(
        "--style-map",
        type=str,
        default=None,
        help='JSON mapping of style names to heading levels, e.g. \'{"a5": 1, "a6": 2}\''
    )

    parser.add_argument(
        "--no-embed-images",
        action="store_true",
        default=False,
        help="Embed images as base64 data URIs instead of separate files. "
             "Produces a self-contained markdown file that can be piped through "
             "OL → pandoc without requiring the image directory."
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

    parser.add_argument(
        "--ocr-engine",
        choices=["tesseract", "rapidocr"],
        default=None,
        help="OCR engine to use for image files (default: tesseract if installed)"
    )

    parser.add_argument(
        "--ocr-lang",
        type=str,
        default=None,
        help="Language for Tesseract OCR (e.g., eng, chi_sim) (default: eng)"
    )

    parser.add_argument(
        "--asr-engine",
        choices=["whisper"],
        default=None,
        help="ASR engine for audio files (default: whisper)"
    )

    parser.add_argument(
        "--model-size",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        default="tiny",
        help="Whisper model size for ASR (default: tiny)"
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: config/default.yaml; opp_config.yaml also accepted with deprecation warning)"
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip the .omni_cache/ cache check (force a fresh extraction)"
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Remove all cached OPP outputs and exit"
    )

    parser.add_argument(
        "--max-file-size", "--max-file-size-mb",
        type=int, default=0,
        help="拒绝超过此大小 (MB) 的文件 (默认: 不限制)"
    )

    parser.add_argument(
        "--log-format",
        choices=["console", "json"],
        default=None,
        help="日志输出格式 (默认: console)。也可通过 OMNI_LOG_FORMAT 环境变量设置。",
    )

    parser.add_argument(
        "--load-dotenv",
        action="store_true",
        help="Load .env file before running (opt-in)"
    )

    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Print OPP module capabilities (input formats, output formats, available tools) and exit"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load .env early so env vars are available for config, LLM auth, etc.
    if args.load_dotenv or os.environ.get("OPP_AUTOLOAD_DOTENV") == "1":
        _load_env_for_opp()

    if args.target_format in ("xlf", "both") and not args.target_lang:
        parser.error("--target-lang is required when --target-format is 'xlf' or 'both'")

    logger = setup_logger(args.verbose)

    if args.clear_cache:
        # A6: short-circuit: clear the cache and exit before any work.
        n = _clear_opp_cache()
        logger.info(f"Cleared {n} cached file(s) from {_cache_root()}")
        return 0

    if args.capabilities:
        # Print module capabilities and exit
        import asyncio as _asyncio
        from opp.mcp.tools.get_capabilities import get_capabilities as _get_caps
        result = _asyncio.run(_get_caps())
        import json as _json
        if result.get("success"):
            content = result["content"]
            print(f"Module: {content.get('module')}")
            print(f"Version: {content.get('version')}")
            print(f"Input formats ({len(content.get('input_formats', []))}): {', '.join(content.get('input_formats', []))}")
            print(f"Output formats: {', '.join(content.get('output_formats', []))}")
            print(f"Tools ({len(content.get('tools', []))}):")
            for tool in content.get("tools", []):
                print(f"  - {tool}")
        else:
            print(_json.dumps(result, indent=2), file=sys.stderr)
        return 0

    # B1: Restrict --resource-dir to prevent path traversal.
    # Allowlist: project root, /tmp, and OPP_ALLOWED_DIRECTORIES env var.
    if args.resource_dir:
        resolved = args.resource_dir.resolve()
        allowed_dirs = [Path.cwd().resolve(), Path("/tmp").resolve()]
        env_allowed = os.environ.get("OPP_ALLOWED_DIRECTORIES", "")
        if env_allowed.strip():
            allowed_dirs.extend(Path(d).resolve() for d in env_allowed.split(",") if d.strip())
        if not any(str(resolved).startswith(str(a)) for a in allowed_dirs):
            parser.error(
                f"Error: --resource-dir '{resolved}' is not within allowed directories. "
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

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

    pipeline = OPPPipeline(
        resource_storage_dir=args.resource_dir or (Path.cwd() / "resources"),
        config_path=args.config,
    )

    stats = batch_process(args, pipeline, stats, error_handler, logger, all_files)

    logger.info(f"Completed: {stats['files_processed']} succeeded, {stats['errors']} failed")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        from opp.logger import get_logger
        get_logger().exception("Uncaught exception in main")
        sys.exit(1)
