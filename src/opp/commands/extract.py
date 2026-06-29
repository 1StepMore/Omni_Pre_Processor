"""File extraction command — ``process_single_file``.

Extracted from ``cli.py`` during the Task 3.7 split. The function is
re-exported from ``opp.cli`` for backward compatibility with tests that
patch ``opp.cli.process_single_file``.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from opp.detector import FormatType
from opp.error_handler import ErrorHandler
from opp.logger import get_logger
from opp.pipeline import OPPPipeline, ProcessingResult
from opp.cliutils import (
    _compute_file_md5,
    _count_xliff_units,
    _detect_format_from_extension,
    get_opp_version,
)


def process_single_file(
    file_path: Path,
    args: argparse.Namespace,
    pipeline: OPPPipeline,
    stats: dict,
    _error_handler: ErrorHandler,
) -> bool:
    """Extract a single document file through the OPP pipeline.

    Parameters
    ----------
    file_path:
        Path to the input document.
    args:
        Parsed CLI arguments (argparse.Namespace).
    pipeline:
        Initialised OPPPipeline instance.
    stats:
        Mutable dict tracking ``files_processed`` / ``errors`` counters.
    _error_handler:
        ErrorHandler instance (currently unused by the function body but
        kept in the signature for backward compatibility).

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure.
    """
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

        if args.target_format in ("html", "both"):
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
