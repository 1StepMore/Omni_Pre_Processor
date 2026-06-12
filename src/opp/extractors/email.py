from email import policy
from email.parser import BytesParser
from os.path import basename
from pathlib import Path
from typing import TYPE_CHECKING
import logging
import re

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    AttachmentData,
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError
from opp.logger import logger

if TYPE_CHECKING:
    from opp.pipeline import OPPPipeline
    from opp.pipeline import ProcessingResult


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
            with open(path, "rb") as f:
                msg = BytesParser(policy=policy.default).parse(f)
        except Exception:
            raise CorruptedFileError(f"Cannot parse EML file: {path}")

        warnings: list[str] = []
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" and not body:
                    try:
                        body = str(part.get_content())
                    except Exception as e:
                        warnings.append(f"Body decode warning: {str(e)}")
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html" and not body:
                    try:
                        body = str(part.get_content())
                    except Exception as e:
                        warnings.append(f"HTML body decode warning: {str(e)}")
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="replace")
        else:
            try:
                body = str(msg.get_content())
            except Exception as e:
                body = ""
                warnings.append(f"Non-multipart body decode warning: {str(e)}")
            if "\ufffd" in body:
                warnings.append("Body contains invalid UTF-8 sequences, used replacement characters")
            elif body:
                try:
                    body.encode("utf-8").decode("utf-8")
                except UnicodeDecodeError:
                    warnings.append("Body contains invalid UTF-8 sequences, used replacement characters")

        paragraphs = [ParagraphData(text=body or "", level=0, style="Normal")]

        attachments: list[AttachmentData] = []
        for part in msg.iter_attachments():
            filename = part.get_filename()
            if not filename:
                continue
            try:
                att_data = part.get_payload(decode=True)
                if not isinstance(att_data, bytes):
                    att_data = b""
            except Exception as e:
                logger.debug(f"Failed to decode email attachment: {e}")
                att_data = b""
            attachments.append(
                AttachmentData(
                    filename=filename,
                    mime_type=part.get_content_type() or "application/octet-stream",
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

        import tempfile
        import os as _os
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