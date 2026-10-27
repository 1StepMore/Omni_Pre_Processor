import json
import zipfile
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import pytest

from opp.extractors.email import EmailExtractor
from opp.utils.exceptions import CorruptedFileError

PLAIN_BODY = (
    "Para one\n\nPara two\n\nPara three\n\n"
    "> quote a\n> quote b\n> quote c\n> quote d\n"
)


def _write_eml(
    tmp_path: Path,
    body: str | None = None,
    html: str | None = None,
    attachments_only: bool = False,
    attachment: bool = False,
) -> Path:
    msg = EmailMessage()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "EML skeleton test"
    if attachments_only:
        msg.make_mixed()
        msg.add_attachment(
            b"attachment bytes",
            maintype="application",
            subtype="octet-stream",
            filename="file.bin",
        )
    elif html is not None:
        msg.set_content(html, subtype="html")
    else:
        msg.set_content(body or "")
    if attachment and not attachments_only:
        msg.add_attachment(
            b"attachment bytes",
            maintype="application",
            subtype="octet-stream",
            filename="file.bin",
        )
    path = tmp_path / "sample.eml"
    path.write_bytes(msg.as_bytes())
    return path


def test_plain_body_splits_paragraphs_and_quote(tmp_path: Path):
    result = EmailExtractor().extract(_write_eml(tmp_path, body=PLAIN_BODY))

    assert len(result.paragraphs) == 4
    assert [p.text for p in result.paragraphs[:3]] == [
        "Para one",
        "Para two",
        "Para three",
    ]
    assert result.paragraphs[-1].style == "Quote"
    assert result.paragraphs[-1].text == "> quote a\n> quote b\n> quote c\n> quote d"


def test_plain_body_splits_signature(tmp_path: Path):
    body = PLAIN_BODY + "\n-- \nJohn Doe\nACME\n"
    result = EmailExtractor().extract(_write_eml(tmp_path, body=body))

    assert len(result.paragraphs) == 5
    assert result.paragraphs[-1].style == "Signature"
    assert result.paragraphs[-1].text == "John Doe\nACME"


def test_html_body_splits_five_paragraphs(tmp_path: Path):
    html = "".join(f"<p>Paragraph {i}</p>" for i in range(1, 6))
    result = EmailExtractor().extract(_write_eml(tmp_path, html=html))

    assert len(result.paragraphs) == 5


def test_html_body_preserves_bold_run(tmp_path: Path):
    result = EmailExtractor().extract(
        _write_eml(tmp_path, html="<p>Hello <b>bold</b></p>")
    )

    assert len(result.paragraphs) == 1
    runs = result.paragraphs[0].runs
    assert runs
    assert any(run.bold for run in runs)


def test_eml_skeleton_contains_original_bytes_and_map(tmp_path: Path):
    path = _write_eml(tmp_path, body=PLAIN_BODY, attachment=True)
    result = EmailExtractor().extract(path)

    assert result.skeleton is not None
    with zipfile.ZipFile(BytesIO(result.skeleton)) as archive:
        assert archive.read("message.eml") == path.read_bytes()
        payload = json.loads(archive.read("eml_map.json"))

    assert payload["version"] == 1
    assert payload["body"]["walk_index"] == 1
    assert payload["body"]["content_type"] == "text/plain"
    assert payload["body"]["content_transfer_encoding"] == "7bit"
    assert len(payload["body"]["unit_ids"]) == len(result.paragraphs) == 4


def test_attachment_only_eml_raises_corrupted_file(tmp_path: Path):
    path = _write_eml(tmp_path, attachments_only=True)

    with pytest.raises(CorruptedFileError):
        EmailExtractor().extract(path)
