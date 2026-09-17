"""OPP CLI — Omni Pre-Processor command-line interface.

Entry point: ``opp`` (defined in ``pyproject.toml`` as ``opp.cli:main``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from opp.error_handler import ErrorHandler
from opp.logger import setup_logger, get_logger
from opp.pipeline import OPPPipeline

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
        help="Reject files larger than this size in MB (default: no limit)"
    )

    parser.add_argument(
        "--log-format",
        choices=["console", "json"],
        default=None,
        help="Log output format (default: console). Also configurable via OMNI_LOG_FORMAT env var.",
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

    parser.add_argument(
        "--validate-xliff",
        action="store_true",
        help="Validate an XLIFF 1.2 file (schema + trans-unit content rules) and exit. "
             "Uses --xliff-content (inline) if provided, otherwise --xliff-file."
    )

    parser.add_argument(
        "--json",
        dest="json",
        action="store_true",
        help="Emit exactly one machine-readable JSON object on stdout "
             "(success, output paths, warnings). Human logs/progress go to stderr."
    )

    parser.add_argument(
        "--xliff-content",
        type=str,
        default=None,
        help="Inline XLIFF XML string. Used with --validate-xliff (takes precedence over --xliff-file)."
    )

    parser.add_argument(
        "--xliff-file",
        type=str,
        default=None,
        help="Path to .xlf/.xliff file. Used with --validate-xliff (when --xliff-content is not set)."
    )

    return parser


def _build_json_payload(stats: dict) -> dict:
    """Build the single JSON object emitted on stdout under ``--json`` (T-04).

    Single-file runs merge the file's ``outputs`` and (on failure) ``error``
    to the top level; multi-file runs carry a ``files`` list.
    """
    results = stats.get("results", [])
    payload: dict = {
        "success": stats.get("errors", 0) == 0,
        "warnings": [w for r in results for w in r.get("warnings", [])],
    }
    if len(results) == 1:
        r = results[0]
        payload["file"] = r["file"]
        payload["outputs"] = r.get("outputs", {})
        if not r.get("success", True):
            payload["error"] = r.get("error", "processing failed")
    else:
        payload["files"] = results
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load .env early so env vars are available for config, LLM auth, etc.
    if args.load_dotenv or os.environ.get("OPP_AUTOLOAD_DOTENV") == "1":
        _load_env_for_opp()

    if args.target_format in ("xlf", "both") and not args.target_lang:
        msg = "--target-lang is required when --target-format is 'xlf' or 'both'"
        if args.json:
            print(json.dumps(
                {"success": False, "error": {"code": "OPP_INVALID_ARGS", "message": msg}, "warnings": []},
                ensure_ascii=False,
            ))
            return 2
        parser.error(msg)

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

    if args.validate_xliff:
        # Validate XLIFF and exit
        if not args.xliff_content and not args.xliff_file:
            print("Error: --validate-xliff requires --xliff-content or --xliff-file", file=sys.stderr)
            return 2
        # Call the validator directly (bypass the MCP tool wrapper which
        # requires the validator singleton to be initialized — only the
        # MCP server does that). The CLI uses the validator directly.
        from opp.xliff.validator import XLIFFValidator
        import json as _json
        if args.xliff_content:
            raw_bytes = args.xliff_content.encode("utf-8")
        else:
            raw_bytes = open(args.xliff_file, "rb").read()
        try:
            validator = XLIFFValidator()
            schema_valid, schema_errors = validator.validate_schema(raw_bytes)
            tu_valid, tu_warnings, tu_errors = validator.validate_trans_units(raw_bytes)
        except Exception as e:  # expected: surface validation failure as structured JSON + exit 2
            print(_json.dumps({"success": False, "error": {"code": "OPP_VALIDATE_FAILED", "message": str(e)}}, indent=2), file=sys.stderr)
            return 2
        result = {
            "success": True,
            "content": {
                "is_valid": bool(schema_valid) and bool(tu_valid),
                "schema_valid": bool(schema_valid),
                "trans_units_valid": bool(tu_valid),
                "schema_errors": list(schema_errors or []),
                "trans_unit_errors": list(tu_errors or []),
                "trans_unit_warnings": list(tu_warnings or []),
                "error_count": len(schema_errors or []) + len(tu_errors or []),
                "warning_count": len(tu_warnings or []),
            },
        }
        print(_json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # B1: Restrict --resource-dir to prevent path traversal.
    # Allowlist: project root, the platform temp dir, and OPP_ALLOWED_DIRECTORIES.
    #
    # 2026-09-17 (ADR 0007, same defect family as _parse_allowed_dirs): the temp
    # dir used to be the hardcoded literal ``Path("/tmp")``. On Windows ``/tmp``
    # resolves to ``<current drive>:\tmp`` (``D:\tmp`` here), which has nothing to
    # do with ``tempfile.gettempdir()`` (``C:\Users\...\AppData\Local\Temp``) — so
    # the allowlist line above was untrue on Windows and every real temp-dir
    # ``--resource-dir`` was rejected. ``tempfile.gettempdir()`` IS ``/tmp`` on
    # POSIX, so Linux/CI behaviour is unchanged verbatim.
    #
    # NOTE: this file is scanned by tests/test_phase5_opp_hardening.py (P5-T1),
    # which fails on ANY CJK character in cli.py — keep comments here in English.
    if args.resource_dir:
        # 2026-09-17: reuse the MCP-side parser so comma-separated values keep
        # working on Linux/CI while Windows `;` (os.pathsep) also splits correctly.
        from opp.mcp.config import _parse_allowed_dirs

        resolved = args.resource_dir.resolve()
        allowed_dirs = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
        allowed_dirs.extend(
            p.resolve()
            for p in _parse_allowed_dirs(os.environ.get("OPP_ALLOWED_DIRECTORIES", ""))
        )
        if not any(str(resolved).startswith(str(a)) for a in allowed_dirs):
            parser.error(
                f"Error: --resource-dir '{resolved}' is not within allowed directories. "
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

    if args.verbose:
        logger.info("OPP CLI v0.1.0")
        logger.info(f"Processing {len(args.files)} input(s)")

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
        if args.json:
            print(json.dumps(
                {"success": False, "error": {"code": "OPP_NO_INPUT", "message": "No supported files found"}, "warnings": []},
                ensure_ascii=False,
            ))
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

    if args.json:
        print(json.dumps(_build_json_payload(stats), ensure_ascii=False))

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        from opp.logger import get_logger
        get_logger().exception("Uncaught exception in main")
        if "--json" in sys.argv:
            print(json.dumps(
                {"success": False, "error": {"code": "OPP_INTERNAL_ERROR", "message": str(exc)}, "warnings": []},
                ensure_ascii=False,
            ))
        sys.exit(1)
