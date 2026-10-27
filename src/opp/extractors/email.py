import json
import logging
import re
import zipfile
from email import policy
from email.parser import BytesParser
from io import BytesIO
from os.path import basename
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opp.extractors.base import ExtractorBase
from opp.logger import logger
from opp.utils.dataclasses import (
    AttachmentData,
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError

if TYPE_CHECKING:
    from opp.pipeline import OPPPipeline, ProcessingResult


_HTML_BLOCK_TAGS = ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote")


def _decode_text_part(part: Any, warnings: list[str]) -> str:
    """Decode a MIME text part, recording a warning instead of raising."""
    label = "HTML body" if part.get_content_type() == "text/html" else "Body"
    try:
        return str(part.get_content())
    except Exception as e:
        logger.debug(f"{label} decode warning: {e}")
        warnings.append(f"{label} decode warning: {e}")
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="replace")
    return ""


def _decode_single_part_body(msg: Any, warnings: list[str]) -> str:
    """Decode a non-multipart EML body, keeping the legacy warning texts."""
    try:
        body = str(msg.get_content())
    except Exception as e:
        logger.debug(f"Non-multipart body decode warning: {e}")
        body = ""
        warnings.append(f"Non-multipart body decode warning: {e}")
    if "\ufffd" in body:
        warnings.append("Body contains invalid UTF-8 sequences, used replacement characters")
    return body


def _select_multipart_body(
    msg: Any, warnings: list[str]
) -> tuple[Any | None, int, str]:
    """Pick the first non-empty text/plain part, else the first text/html one."""
    parts = list(msg.walk())
    for index, part in enumerate(parts):
        if part.get_content_type() != "text/plain":
            continue
        body = _decode_text_part(part, warnings)
        if body.strip():
            return part, index, body
    for index, part in enumerate(parts):
        if part.get_content_type() != "text/html":
            continue
        body = _decode_text_part(part, warnings)
        if body.strip():
            return part, index, body
    return None, 0, ""


def _split_plain_body(text: str) -> list[ParagraphData]:
    """Split a text/plain body into paragraphs, quotes, and an RFC 3676 signature."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    signature_start: int | None = None
    for index, line in enumerate(lines):
        if line == "-- ":
            signature_start = index
            break

    body_end = len(lines) if signature_start is None else signature_start
    paragraphs: list[ParagraphData] = []
    block: list[str] = []

    def flush_block() -> None:
        current: list[str] = []
        current_quote: bool | None = None
        for line in block:
            is_quote = line.lstrip().startswith(">")
            if current_quote is not None and is_quote != current_quote:
                paragraphs.append(
                    ParagraphData(
                        text="\n".join(current),
                        style="Quote" if current_quote else "Normal",
                        level=0,
                    )
                )
                current = []
            current.append(line)
            current_quote = is_quote
        if current:
            paragraphs.append(
                ParagraphData(
                    text="\n".join(current),
                    style="Quote" if current_quote else "Normal",
                    level=0,
                )
            )
        block.clear()

    for line in lines[:body_end]:
        if not line.strip():
            flush_block()
        else:
            block.append(line.rstrip())
    flush_block()

    if signature_start is not None:
        signature_text = "\n".join(line.rstrip() for line in lines[signature_start + 1 :]).strip()
        if signature_text:
            paragraphs.append(
                ParagraphData(text=signature_text, style="Signature", level=0)
            )

    return [paragraph for paragraph in paragraphs if paragraph.text]


def _html_body_to_paragraphs(html_str: str) -> list[ParagraphData]:
    """Convert an HTML body to paragraphs/runs without HTMLExtractor.extract().

    Nesting is resolved by preferring the innermost block, so a ``<div>`` that
    merely wraps ``<p>`` children is skipped while ``<li>``/``<blockquote>``
    keep their own style. Calling ``extract()`` would set ``format_type="html"``
    and push ``save_skeleton`` onto its HTML branch, so only ``extract_runs``
    is reused.
    """
    from bs4 import BeautifulSoup

    from opp.extractors.html import HTMLExtractor

    soup = BeautifulSoup(html_str, "html.parser")
    extractor = HTMLExtractor()
    paragraphs: list[ParagraphData] = []
    emitted: list[Any] = []

    for element in soup.find_all(list(_HTML_BLOCK_TAGS)):
        if not element.get_text(strip=True):
            continue
        if element.name not in ("li", "blockquote") and element.find(
            list(_HTML_BLOCK_TAGS)
        ):
            continue
        if any(ancestor is done for ancestor in element.parents for done in emitted):
            continue

        style = None
        level = None
        if element.name == "blockquote":
            style = "Quote"
        elif element.name == "li":
            style = "List"
        elif element.name and element.name[0] == "h" and element.name[1:].isdigit():
            level = int(element.name[1:])

        paragraphs.append(
            ParagraphData(
                text=element.get_text(" ", strip=True),
                style=style,
                level=level,
                runs=extractor.extract_runs(element),
            )
        )
        emitted.append(element)

    if not paragraphs:
        return _split_plain_body(soup.get_text("\n\n", strip=True))
    return paragraphs


def _build_eml_skeleton(
    raw: bytes, walk_index: int, part: Any, paragraphs: list[ParagraphData]
) -> tuple[bytes, list[str]]:
    """Build the EML skeleton: original bytes verbatim plus an ``eml_map.json`` map."""
    line_sep = "\r\n" if b"\r\n" in raw else "\n"
    headers_rebuilt = not (b"\r\n\r\n" in raw or b"\n\n" in raw)
    payload = {
        "version": 1,
        "body": {
            "walk_index": walk_index,
            "content_type": part.get_content_type(),
            "charset": part.get_content_charset() or "utf-8",
            "content_transfer_encoding": (
                part.get("Content-Transfer-Encoding") or "7bit"
            ).lower(),
            "line_sep": line_sep,
            "unit_ids": [str(i) for i in range(1, len(paragraphs) + 1)],
            "joiner": "\n\n",
        },
        "headers_rebuilt": headers_rebuilt,
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("message.eml", raw)
        archive.writestr(
            "eml_map.json",
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return buffer.getvalue(), ["message.eml", "eml_map.json"]


class EmailExtractor(ExtractorBase):

    def supported_extensions(self) -> list[str]:
        return [".eml", ".msg"]

    def extract(self, input_path: Path) -> ExtractionResult:
        self.validate_file(input_path)
        ext = input_path.suffix.lower()
        if ext == ".msg":
            return self._extract_msg(input_path)
        elif ext == ".eml":
            return self._extract_eml(input_path)
        raise CorruptedFileError(f"Unsupported email format: {ext}")

    def _extract_eml(self, path: Path) -> ExtractionResult:
        try:
            raw = path.read_bytes()
            msg = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception:
            logger.debug("Failed to parse EML file: %s", path)
            raise CorruptedFileError(f"Cannot parse EML file: {path}")

        warnings: list[str] = []
        if msg.is_multipart():
            part, walk_index, body = _select_multipart_body(msg, warnings)
        else:
            part = msg
            walk_index = 0
            body = _decode_single_part_body(msg, warnings)

        if part is None or not body.strip():
            raise CorruptedFileError(f"EML has no text body part: {path}")

        if part.get_content_type() == "text/html":
            paragraphs = _html_body_to_paragraphs(body)
        else:
            paragraphs = _split_plain_body(body)

        if not paragraphs:
            raise CorruptedFileError(f"EML has no text body part: {path}")

        skeleton_bytes, skeleton_files = _build_eml_skeleton(
            raw, walk_index, part, paragraphs
        )

        attachments: list[AttachmentData] = []
        for attachment_part in msg.iter_attachments():
            filename = attachment_part.get_filename()
            if not filename:
                continue
            try:
                att_data = attachment_part.get_payload(decode=True)
                if not isinstance(att_data, bytes):
                    att_data = b""
            except Exception as e:
                logger.debug(f"Failed to decode email attachment: {e}")
                att_data = b""
            attachments.append(
                AttachmentData(
                    filename=filename,
                    mime_type=attachment_part.get_content_type() or "application/octet-stream",
                    data=att_data,
                )
            )

        metadata = DocumentMetadata(
            file_size=path.stat().st_size,
            format_type="EMAIL",
            page_count=1,
            subject=msg["subject"] or None,
            sender=msg["sender"] or msg["from"] or None,
            to=msg["to"] or None,
            cc=msg["cc"] or None,
            date=msg["date"] or None,
        )

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            attachments=attachments,
            metadata=metadata,
            warnings=warnings,
            skeleton=skeleton_bytes,
            skeleton_files=skeleton_files,
            table_row_paragraph_indices=frozenset(),
        )

    def _extract_msg(self, path: Path) -> ExtractionResult:
        try:
            import extract_msg
        except ImportError:
            raise CorruptedFileError(f"extract_msg library not installed for MSG parsing: {path}")

        try:
            msg = extract_msg.Message(str(path))
        except ImportError:
            raise CorruptedFileError(f"extract_msg library not available for MSG parsing: {path}")
        except Exception as e:
            logger.debug(f"Failed to parse MSG file: {e}")
            error_str = str(e).lower()
            if "encrypted" in error_str or "password" in error_str:
                raise PasswordProtectedError(f"MSG file is encrypted: {path}")
            raise CorruptedFileError(f"Cannot parse MSG file: {path}")

        metadata = DocumentMetadata(
            file_size=path.stat().st_size,
            format_type="EMAIL",
            page_count=1,
            subject=msg.subject or None,
            sender=msg.sender or None,
            to=msg.to or None,
            cc=msg.cc or None,
            date=str(msg.date) if hasattr(msg, "date") and msg.date else None,
        )

        body = msg.body or ""
        if not body:
            try:
                html_body_bytes = msg.htmlBody
                if html_body_bytes:
                    body = html_body_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                logger.debug(f"Failed to decode HTML body: {e}")
                body = ""

        paragraphs = [ParagraphData(text=body, level=0, style="Normal")]

        attachments = []
        for att in msg.attachments:
            att_name = att.name or "unknown_attachment"
            att_data: bytes = b""
            raw_data = getattr(att, "data", None)
            if raw_data and isinstance(raw_data, bytes):
                att_data = raw_data
            att_mime = getattr(att, "mimetype", None) or "application/octet-stream"
            attachments.append(
                AttachmentData(
                    filename=att_name,
                    mime_type=att_mime,
                    data=att_data,
                )
            )

        warnings = []

        return ExtractionResult(
            paragraphs=paragraphs,
            tables=[],
            images=[],
            attachments=attachments,
            metadata=metadata,
            warnings=warnings,
        )


class AttachmentHandler:
    def __init__(self, pipeline: "OPPPipeline", max_depth: int = 3) -> None:
        self.pipeline = pipeline
        self.max_depth = max_depth
        self._current_depth = 0
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize attachment filename to prevent path traversal."""
        filename = basename(filename)
        filename = re.sub(r"[^\w\s\-.]", "_", filename)
        if not filename or filename.startswith("."):
            filename = "attachment"
        return filename

    def process_attachment(self, attachment_data: AttachmentData) -> "ProcessingResult | None":
        if self._current_depth >= self.max_depth:
            self._logger.debug(
                "process_attachment: skipping attachment '%s' (recursion depth %d >= max %d)",
                attachment_data.filename, self._current_depth, self.max_depth,
            )
            return None

        original_filename = attachment_data.filename
        safe_filename = self._sanitize_filename(original_filename)
        if safe_filename != original_filename:
            self._logger.warning(
                "Attachment filename sanitized to prevent path traversal: "
                "%s -> %s", original_filename, safe_filename
            )

        import os as _os
        import tempfile
        fd, temp_path_str = tempfile.mkstemp(suffix=_os.path.splitext(safe_filename)[1], prefix="opp_email_")
        _os.close(fd)
        temp_path = Path(temp_path_str)
        try:
            with open(temp_path, "wb") as f:
                f.write(attachment_data.data)

            self._current_depth += 1
            result = self.pipeline.process_file(temp_path)
            self._current_depth -= 1

            return result
        except Exception as e:
            logger.debug(
                f"process_attachment: attachment '{attachment_data.filename}' processing failed: {e}"
            )
            return None
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @property
    def recursion_depth(self) -> int:
        return self._current_depth