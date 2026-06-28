import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from opp.detector import FormatType, detect_format
from opp.error_handler import ErrorHandler, ErrorContext
from opp.pipeline import OPPPipeline, ProcessingResult
from opp.logger import setup_logger, get_logger
from opp.utils.cache import cache_root


# ========== A6: Content-addressed cache (~/.omni_cache/opp/) ==========
# Re-runs of the same input+config skip the expensive extraction and just
# copy the cached .xlf to the output dir. The cache root can be overridden
# with the OMNI_CACHE_DIR env var (used by tests). Mode 0o700 protects any
# sensitive content (e.g., a translated DOCX that contains private info).
# CACHE_DIR is computed lazily so the OMNI_CACHE_DIR override works even
# when tests set the env var after the module is imported.
CACHE_DIR_NAME = "opp"


def _cache_root() -> Path:
    """Return the OPP cache root, delegating to the shared utility."""
    return cache_root(CACHE_DIR_NAME)


def _cache_key(input_path: Path, config: dict) -> str:
    """Return sha256(input_bytes + repr(sorted(config.items())))."""
    h = hashlib.sha256()
    h.update(input_path.read_bytes())
    h.update(repr(sorted(config.items())).encode())
    return h.hexdigest()


def _relevant_config_for_cache(args: argparse.Namespace) -> dict:
    """Build the config dict that affects the cache key for OPP.

    Only the user-supplied ``--config`` file is hashed; CLI flags like
    --source-lang/--target-lang are NOT in the cache key because they are
    typically derived from the config file (and including them would
    invalidate the cache for any CLI override of an unchanged config).
    """
    if args.config and args.config.exists():
        return {
            "config_file_sha256": hashlib.sha256(
                args.config.read_bytes()
            ).hexdigest()
        }
    return {}


def _check_cache(file_path: Path, args: argparse.Namespace, output_dir: Path) -> bool:
    """If cached, copy ``<stem>.xlf`` to ``output_dir`` and return True."""
    if getattr(args, "no_cache", False):
        return False
    key = _cache_key(file_path, _relevant_config_for_cache(args))
    cache_file = _cache_root() / f"{key}.xlf"
    if cache_file.exists():
        target = output_dir / f"{file_path.stem}.xlf"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(cache_file, target)
        get_logger().info(f"Cache hit: {cache_file} -> {target}")
        return True
    return False


def _write_cache(file_path: Path, args: argparse.Namespace, output_dir: Path) -> None:
    """Copy the produced .xlf into the cache for next run."""
    if getattr(args, "no_cache", False):
        return
    output_file = output_dir / f"{file_path.stem}.xlf"
    if not output_file.exists():
        return
    key = _cache_key(file_path, _relevant_config_for_cache(args))
    cache_file = _cache_root() / f"{key}.xlf"
    cache_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy(output_file, cache_file)
    get_logger().debug(f"Cache miss: wrote {cache_file}")


def _clear_opp_cache() -> int:
    """Remove all cached OPP files. Returns the number of files removed."""
    root = _cache_root()
    if not root.exists():
        return 0
    count = sum(1 for _ in root.iterdir())
    shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return count


def _load_env_for_opp() -> None:
    """Load .env file for OPP CLI commands.

    Search order:
      1. $OPP_DOTENV env var (explicit override)
      2. ./.env (current working directory)
      3. Walk up parent directories looking for .env
      4. ~/.config/opp/.env (user-level fallback)

    If no .env is found, the function returns silently.
    """
    import os
    from pathlib import Path

    search_paths: list[Path] = []
    explicit = os.environ.get("OPP_DOTENV")
    if explicit:
        search_paths.append(Path(explicit))
    search_paths.append(Path.cwd() / ".env")
    for parent in Path.cwd().resolve().parents:
        candidate = parent / ".env"
        if candidate not in search_paths:
            search_paths.append(candidate)
    search_paths.append(Path.home() / ".config" / "opp" / ".env")

    for env_path in search_paths:
        if env_path.exists() and env_path.is_file():
            _load_dotenv_for_opp(env_path)
            return


def _load_dotenv_for_opp(env_path: Path) -> None:
    """Parse and export .env file without blocking on missing keys."""
    import os
    try:
        content = env_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
    except Exception as exc:
        from opp.logger import get_logger
        get_logger().warning("Failed to load .env file %s: %s", env_path, exc)


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

    return parser


def get_supported_extensions() -> list[str]:
    return ['.docx', '.pptx', '.pdf', '.html', '.epub', '.eml', '.msg', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']


def expand_directories(paths: list[Path]) -> list[Path]:
    files = []
    for path in paths:
        if path.is_dir():
            supported_exts = get_supported_extensions()
            for ext in supported_exts:
                for f in path.rglob(f'*{ext}'):
                    if not f.name.startswith('.') and f.is_file():
                        files.append(f)
        elif path.is_file():
            files.append(path)
    return files


def _detect_format_from_extension(path: Path) -> str:
    """Detect format type from file extension."""
    ext = path.suffix.lower()
    format_map = {
        ".docx": "DOCX", ".pptx": "PPTX", ".pdf": "PDF",
        ".xlsx": "XLSX", ".html": "HTML", ".xml": "XML",
        ".json": "JSON", ".csv": "CSV", ".epub": "EPUB",
        ".eml": "EML", ".msg": "MSG", ".md": "MARKDOWN",
        ".xlf": "XLIFF", ".xliff": "XLIFF",
    }
    return format_map.get(ext, "UNKNOWN")

def _compute_file_md5(path: Path) -> str:
    """Compute MD5 hash of file using chunked reading."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()

def _count_xliff_units(xliff_path: Path) -> int:
    """Count trans-unit elements in XLIFF file."""
    import re
    content = xliff_path.read_text(encoding="utf-8")
    return len(re.findall(r'<trans-unit[^>]*>', content))

def get_opp_version() -> str:
    """Return OPP version string."""
    from opp import __version__
    return __version__


def process_single_file(
    file_path: Path,
    args: argparse.Namespace,
    pipeline: OPPPipeline,
    stats: dict,
    _error_handler: ErrorHandler
) -> bool:
    try:
        if getattr(args, "log_format", None):
            os.environ["OMNI_LOG_FORMAT"] = args.log_format

        if args.ocr_engine:
            os.environ["OPP_OCR_ENGINE"] = args.ocr_engine
        if args.ocr_lang:
            os.environ["OPP_OCR_LANG"] = args.ocr_lang

        if args.asr_engine:
            os.environ["OPP_ASR_ENGINE"] = args.asr_engine
        if args.model_size:
            os.environ["OPP_MODEL_SIZE"] = args.model_size

        # PDF + html/both: use PDF2HTMLExtractor directly (before process_file)
        if args.target_format in ("html", "both") and file_path.suffix.lower() == ".pdf":
            from opp.extractors.pdf2html import PDF2HTMLExtractor
            try:
                pdf2html = PDF2HTMLExtractor()
                extraction_result = pdf2html.extract(file_path)
                proc_result = ProcessingResult(
                    content=extraction_result.content,
                    format_type=FormatType.HTML,
                    images_stored=0,
                    extraction_result=extraction_result,
                )
            except Exception as e:
                stats["errors"] += 1
                get_logger().error(f"PDF2HTML extraction failed for {file_path}: {e}")
                return False
        else:
            proc_result = pipeline.process_file(file_path)
        # 2026-06-18 round 16 Phase B2: end-to-end request_id.
        request_id = str(uuid.uuid4())

        if proc_result.errors:
            stats["errors"] += 1
            for error in proc_result.errors:
                get_logger().error(f"{file_path}: {error}")
            return False

        if proc_result.extraction_result is None:
            stats["errors"] += 1
            get_logger().error(f"No extraction result for {file_path}")
            return False

        output_dir = args.output_dir if args.output_dir else file_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = file_path.stem

        style_mapping = json.loads(args.style_map) if args.style_map else None

        if args.target_format in ("md", "both"):
            md_path = output_dir / f"{base_name}.md"
            pipeline.generate_markdown(
                proc_result.extraction_result, md_path, proc_result.attachment_results,
                style_mapping=style_mapping, embed_images=not args.no_embed_images,
            )
            get_logger().info(f"Generated: {md_path}")

        if args.target_format in ("xlf", "both"):
            xliff_path = output_dir / f"{base_name}.xlf"
            pipeline.generate_xliff(
                proc_result.extraction_result,
                xliff_path,
                args.source_lang,
                args.target_lang,
                request_id=request_id,
            )
            get_logger().info(f"Generated: {xliff_path}")

        if args.target_format == "html":
            html_out_path = output_dir / f"{base_name}.html"
            if proc_result.extraction_result and proc_result.extraction_result.skeleton_html:
                html_out_path.write_text(
                    proc_result.extraction_result.skeleton_html, encoding="utf-8"
                )
                get_logger().info(f"Generated: {html_out_path}")
            else:
                get_logger().warning(f"No HTML skeleton available for {file_path}")

        # Always emit images.json when images are present (POST_MORTEM OPP-1).
        images_json_path: Path | None = None
        if proc_result.extraction_result is not None and proc_result.extraction_result.images:
            images_json_path = output_dir / f"{base_name}_images.json"
            pipeline.generate_images_json(
                proc_result.extraction_result, images_json_path
            )
            get_logger().info(f"Generated: {images_json_path}")

        md_path = output_dir / f"{base_name}.md"
        xliff_path = output_dir / f"{base_name}.xlf"

        try:
            file_size = file_path.stat().st_size
            file_hash = _compute_file_md5(file_path)
        except OSError as e:
            stats["errors"] += 1
            get_logger().error(f"Cannot access file {file_path}: {e}")
            return False

        manifest = {
            "manifest_version": "1.0",
            "request_id": request_id,
            "generated_at": datetime.now().isoformat() + "Z",
            "tool": "OPP",
            "tool_version": get_opp_version(),
            "source": {
                "file_path": str(file_path.resolve()),
                "original_filename": file_path.name,
                "format": _detect_format_from_extension(file_path),
                "file_size_bytes": file_size,
                "file_hash_md5": file_hash,
            },
            "extraction": {
                "source_lang": args.source_lang or "zh",
                "target_lang": args.target_lang or "en",
                "outputs": {
                    "markdown": {
                        "path": str(md_path.relative_to(output_dir)) if md_path.exists() else None,
                        "paragraph_count": len(proc_result.extraction_result.paragraphs) if proc_result.extraction_result else 0,
                        "table_count": len(proc_result.extraction_result.tables) if proc_result.extraction_result else 0,
                    },
                    "xliff": {
                        "path": str(xliff_path.relative_to(output_dir)) if xliff_path.exists() else None,
                        "trans_unit_count": _count_xliff_units(xliff_path) if xliff_path.exists() else 0,
                    },
                    "images_json": {
                        "path": str(images_json_path.relative_to(output_dir)) if images_json_path and images_json_path.exists() else None,
                    } if images_json_path is not None else None,
                },
                "images": [
                    {
                        "mime_type": img.mime_type,
                        "width": img.width,
                        "height": img.height,
                        "data_size_bytes": len(img.data),
                    }
                    for img in (proc_result.extraction_result.images if proc_result.extraction_result else [])
                ],
                "warnings": proc_result.extraction_result.warnings if proc_result.extraction_result else [],
            },
            "resources": {
                "storage_dir": str(args.resource_dir.resolve()) if args.resource_dir else str(Path.cwd() / "resources"),
                "image_count": len(proc_result.extraction_result.images) if proc_result.extraction_result else 0,
            },
        }
        manifest_path = output_dir / f"{base_name}_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        get_logger().info(f"Manifest written: {manifest_path}")

        # ========== Save skeleton.zip ==========
        skeleton_path = pipeline.save_skeleton(
            proc_result.extraction_result,
            base_name,
            output_dir
        )
        if skeleton_path:
            get_logger().info(f"Skeleton saved: {skeleton_path}")
            manifest["skeleton"] = {
                "path": str(skeleton_path.relative_to(output_dir)),
                "format": "ZIP",
                "key_files": proc_result.extraction_result.skeleton_files,
            }
            # Re-write manifest with skeleton info
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        stats["errors"] += 1
        get_logger().exception(f"Error processing {file_path}: {e}")
        return False


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

    pipeline = OPPPipeline(resource_storage_dir=args.resource_dir or (Path.cwd() / "resources"), config_path=args.config)

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
            # P0-3: file size limit check before any expensive work.
            if args.max_file_size > 0:
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > args.max_file_size:
                    logger.warning("跳过 %s: 文件大小 %.1fMB 超过限制 %dMB", file_path, file_size_mb, args.max_file_size)
                    stats["errors"] += 1
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
                    continue
            success = process_single_file(file_path, args, pipeline, stats, error_handler)
            if success:
                # A6: cache the produced .xlf so the next run is a cache hit.
                _write_cache(file_path, args, output_dir)
                stats["files_processed"] += 1
        else:
            logger.warning(
                "--target-format not specified for %s; no output files "
                "generated. Use --target-format md, xlf, both, or html.",
                file_path,
            )
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
    try:
        sys.exit(main())
    except Exception:
        from opp.logger import get_logger
        get_logger().exception("Uncaught exception in main")
        sys.exit(1)
