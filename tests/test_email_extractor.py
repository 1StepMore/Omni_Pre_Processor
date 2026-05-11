from pathlib import Path
import pytest
from datetime import datetime

from opp.extractors.email import EmailExtractor


class TestEmailExtractor:
    def test_extract_msg_metadata(self, tmp_path: Path):
        import extract_msg

        msg_path = tmp_path / "test_email.msg"
        from extract_msg import Message

        msg = Message(
            str(msg_path),
            to="recipient@example.com",
            sender="sender@example.com",
            subject="Test Subject",
            date=datetime.now(),
            body="Test body content",
            skip_attachments=True,
        )
        msg.save()

        extractor = EmailExtractor()
        result = extractor.extract(msg_path)

        assert result.metadata is not None
        assert "subject" in dir(result.metadata) or hasattr(result.metadata, "subject")

    def test_extract_eml_metadata(self, tmp_path: Path):
        from email.message import EmailMessage

        eml_path = tmp_path / "test_email.eml"
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Test EML Subject"
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
        msg.set_content("Test body content")

        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        extractor = EmailExtractor()
        result = extractor.extract(eml_path)

        assert result.metadata is not None
        assert "subject" in dir(result.metadata) or hasattr(result.metadata, "subject")

    def test_extract_msg_body(self, tmp_path: Path):
        from extract_msg import Message

        msg_path = tmp_path / "body_test.msg"
        msg = Message(
            str(msg_path),
            to="test@example.com",
            sender="sender@example.com",
            subject="Body Test",
            date=datetime.now(),
            body="This is the plain text body content",
            skip_attachments=True,
        )
        msg.save()

        extractor = EmailExtractor()
        result = extractor.extract(msg_path)

        body_text = result.content
        assert "plain text body" in body_text
        assert len(result.paragraphs) >= 1

    def test_extract_eml_html_body(self, tmp_path: Path):
        from email.message import EmailMessage

        eml_path = tmp_path / "html_body.eml"
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "HTML Body Test"
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

        html_content = "<html><body><p>HTML <strong>bold</strong> content</p></body></html>"
        msg.set_content(html_content, subtype="html")

        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        extractor = EmailExtractor()
        result = extractor.extract(eml_path)

        body_text = result.content
        assert "HTML" in body_text
        assert "bold" in body_text

    def test_extract_msg_attachments(self, tmp_path: Path):
        from extract_msg import Message

        attachment_path = tmp_path / "attachment.txt"
        attachment_path.write_text("This is an attachment content")

        msg_path = tmp_path / "with_attachments.msg"
        msg = Message(
            str(msg_path),
            to="test@example.com",
            sender="sender@example.com",
            subject="Attachment Test",
            date=datetime.now(),
            body="Email with attachments",
            skip_attachments=False,
        )

        extractor = EmailExtractor()
        result = extractor.extract(msg_path)

        assert hasattr(result, "attachments") or hasattr(result, "images")

    def test_extract_eml_attachments(self, tmp_path: Path):
        from email.message import EmailMessage
        import base64

        eml_path = tmp_path / "eml_with_attachments.eml"
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "EML Attachment Test"
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

        attachment_data = b"Attachment file content"
        encoded_data = base64.b64encode(attachment_data).decode()

        msg.set_content("Email body with attachment")
        msg.add_attachment(
            "test_file.txt",
            ("text/plain", "attachment", None, None, encoded_data, None),
        )

        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        extractor = EmailExtractor()
        result = extractor.extract(eml_path)

        assert hasattr(result, "attachments") or hasattr(result, "images")

    def test_corrupted_msg(self, tmp_path: Path):
        corrupted_msg_path = tmp_path / "corrupted.msg"
        corrupted_msg_path.write_bytes(b"This is not a valid MSG file at all")

        extractor = EmailExtractor()
        from opp.utils.exceptions import CorruptedFileError

        with pytest.raises(CorruptedFileError):
            extractor.extract(corrupted_msg_path)

    def test_encoding_error_eml(self, tmp_path: Path):
        encoding_error_path = tmp_path / "encoding_error.eml"

        raw_content = (
            b"From: sender@example.com\r\n"
            b"To: recipient@example.com\r\n"
            b"Subject: Encoding Test\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"\xff\xfe\xfd\xfc"
        )
        encoding_error_path.write_bytes(raw_content)

        extractor = EmailExtractor()
        result = extractor.extract(encoding_error_path)

        assert len(result.warnings) >= 1