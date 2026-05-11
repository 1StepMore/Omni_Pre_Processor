from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import List

from opp.extractors.base import ExtractorBase
from opp.utils.dataclasses import (
    AttachmentData,
    DocumentMetadata,
    ExtractionResult,
    ParagraphData,
)
from opp.utils.exceptions import CorruptedFileError, PasswordProtectedError


class EmailExtractor(ExtractorBase):

    def supported_extensions(self) -> List[str]:
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
        except Exception as e:
            raise CorruptedFileError(f"Cannot parse EML file: {path}")

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" and not body:
                    try:
                        body = str(part.get_content())
                    except Exception:
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html" and not body:
                    try:
                        body = str(part.get_content())
                    except Exception:
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="replace")
        else:
            try:
                body = str(msg.get_content())
            except Exception:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body = payload.decode("utf-8", errors="replace")

        paragraphs = [ParagraphData(text=body or "", level=0, style="Normal")]

        attachments: List[AttachmentData] = []
        for part in msg.iter_attachments():
            filename = part.get_filename()
            if not filename:
                continue
            try:
                att_data = part.get_payload(decode=True)
                if not isinstance(att_data, bytes):
                    att_data = b""
            except Exception:
                att_data = b""
            attachments.append(
                AttachmentData(
                    filename=filename,
                    mime_type=part.get_content_type() or "application/octet-stream",
                    data=att_data,
                )
            )

        warnings: List[str] = []
        metadata = DocumentMetadata(
            file_size=path.stat().st_size,
            format_type="EMAIL",
            page_count=1,
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
        import extract_msg

        try:
            msg = extract_msg.Message(str(path))
        except Exception as e:
            error_str = str(e).lower()
            if "encrypted" in error_str or "password" in error_str:
                raise PasswordProtectedError(f"MSG file is encrypted: {path}")
            raise CorruptedFileError(f"Cannot parse MSG file: {path}")

        metadata = DocumentMetadata(
            file_size=path.stat().st_size,
            format_type="EMAIL",
            page_count=1,
        )

        body = msg.body or ""
        if not body:
            try:
                html_body_bytes = msg.htmlBody
                if html_body_bytes:
                    body = html_body_bytes.decode("utf-8", errors="replace")
            except Exception:
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