"""Batch processing command for OPP CLI.

Extracted from ``cli.py`` during the Task 3.7 split. Contains the
file-processing loop that was previously inline in ``main()``.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from opp.detector import FormatType, detect_format
from opp.error_handler import ErrorContext
from opp.pipeline import PDF_XLIFF_UNSUPPORTED_MSG
from opp.cliutils import (
    _check_cache,
    _write_cache,
)


def _collect_existing_outputs(output_dir: Path, stem: str) -> dict:
    """Return the OPP output paths that actually exist for ``stem`` (T-04).

    Only paths present on disk are reported — the JSON output must never
    claim an artifact that was not produced (no misleading success output).
    """
    candidates = {
        "md": output_dir / f"{stem}.md",
        "xliff": output_dir / f"{stem}.xlf",
        "html": output_dir / f"{stem}.html",
        "images_json": output_dir / f"{stem}_images.json",
        "manifest": output_dir / f"{stem}_manifest.json",
        "skeleton": output_dir / f"{stem}.skeleton.zip",
    }
    return {k: str(p.resolve()) for k, p in candidates.items() if p.exists()}


def _synth_result(
    file_path: Path,
    output_dir: Path,
    success: bool,
    error: str | None = None,
) -> dict:
    """Synthesize a result record for paths that skip ``process_single_file``.

    Used for cache hits, guards, and mocked ``process_single_file`` (tests):
    those paths never append a real record, so ``batch_process`` fills the
    gap to keep the ``--json`` report complete.
    """
    record = {
        "file": str(file_path),
        "success": success,
        "outputs": _collect_existing_outputs(output_dir, file_path.stem),
        "warnings": [],
    }
    if error:
        record["error"] = error
    return record



def batch_process(
    args,
    pipeline,
    stats: dict,
    error_handler,
    logger,
    all_files: list[Path],
) -> dict:
    """Process multiple files through the OPP pipeline.

    Handles format detection, file-size limits, caching, per-file
    extraction (via ``process_single_file``), and report generation.

    Parameters
    ----------
    args:
        Parsed CLI arguments (argparse.Namespace).
    pipeline:
        Initialised OPPPipeline instance.
    stats:
        Mutable dict tracking ``files_processed`` / ``errors`` counters.
    error_handler:
        ErrorHandler instance.
    logger:
        Logger instance.
    all_files:
        List of file paths to process (already expanded by
        ``expand_directories``).

    Returns
    -------
    dict
        The updated ``stats`` dict with final counters and duration.
    """
    # Lazy import so patch("opp.cli.process_single_file") in tests takes effect.
    from opp.cli import process_single_file

    start_time = time.time()
    stats.setdefault("results", [])

    for i, file_path in enumerate(all_files, 1):
        if args.verbose:
            logger.info(f"[{i}/{len(all_files)}] Processing: {file_path}")

        if args.detect_format:
            fmt, confidence = detect_format(file_path)
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
                stats["results"].append(_synth_result(
                    file_path, file_path.parent, False,
                    error=f"Unknown file format (confidence {confidence})",
                ))
                continue

        if args.target_format:
            # P0-3: file size limit check before any expensive work.
            if args.max_file_size > 0:
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > args.max_file_size:
                    logger.warning("跳过 %s: 文件大小 %.1fMB 超过限制 %dMB", file_path, file_size_mb, args.max_file_size)
                    stats["errors"] += 1
                    stats["results"].append(_synth_result(
                        file_path, file_path.parent, False,
                        error=f"File too large: {file_size_mb:.1f}MB > {args.max_file_size}MB",
                    ))
                    continue

            # PDF→XLIFF guard must fire BEFORE the A6 cache check: a cached
            # .xlf written by a pre-guard run would otherwise replay the
            # bypassed output and the CLI would exit 0 (T2 regression).
            if args.target_format in ("xlf", "both"):
                fmt, _ = detect_format(file_path)
                if fmt == FormatType.PDF:
                    stats["errors"] += 1
                    stats["results"].append(_synth_result(
                        file_path, file_path.parent, False,
                        error=PDF_XLIFF_UNSUPPORTED_MSG,
                    ))
                    print(
                        f"Error processing {file_path}: {PDF_XLIFF_UNSUPPORTED_MSG}",
                        file=sys.stderr,
                    )
                    continue

            # A6: cache check before any expensive work. If the input+config
            # key is in the cache, copy the .xlf to the output dir and skip
            # the full extraction pipeline for this file.
            output_dir = args.output_dir if args.output_dir else file_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            # Cache stores only .xlf. If MD is requested (target_format in
            # ("md", "both")), skip cache so generate_markdown() runs.
            if args.target_format not in ("md", "both", "html"):
                if _check_cache(file_path, args, output_dir):
                    stats["files_processed"] += 1
                    stats["results"].append(_synth_result(file_path, output_dir, True))
                    continue
            results_before = len(stats["results"])
            success = process_single_file(file_path, args, pipeline, stats, error_handler)
            if success:
                # A6: cache the produced .xlf so the next run is a cache hit.
                _write_cache(file_path, args, output_dir)
                stats["files_processed"] += 1
            if len(stats["results"]) == results_before:
                # process_single_file was mocked (tests) or failed without
                # recording — synthesize a record to keep --json complete.
                stats["results"].append(_synth_result(file_path, output_dir, success))
        else:
            logger.warning(
                "--target-format not specified for %s; no output files "
                "generated. Use --target-format md, xlf, both, or html.",
                file_path,
            )
            stats["results"].append(_synth_result(file_path, file_path.parent, True))
            stats["files_processed"] += 1

    # Report generation
    if args.report:
        if args.report == "html":
            report = error_handler.generate_html_report(file_count=stats["files_processed"])
        else:
            report = error_handler.generate_text_report(file_count=stats["files_processed"])

        if args.output:
            args.output.write_text(report, encoding="utf-8")
            logger.info(f"Report saved to: {args.output}")
        else:
            # Under --json the human report would pollute stdout (T-04).
            stream = sys.stderr if getattr(args, "json", False) else sys.stdout
            print("\n" + report, file=stream)

    duration = time.time() - start_time
    stats["duration_seconds"] = duration

    return stats
