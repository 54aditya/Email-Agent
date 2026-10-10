import base64
import email
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import utils


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_strip_html_removes_tags_and_scripts():
    raw = "<html><style>p{}</style><p>Hello&nbsp;<b>World</b></p><script>x()</script></html>"
    assert utils.strip_html(raw) == "Hello World"


def test_extract_body_prefers_plain_text():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": b64("plain body")}},
            {"mimeType": "text/html", "body": {"data": b64("<p>html body</p>")}},
        ],
    }
    assert utils.extract_body(payload) == "plain body"


def test_extract_body_falls_back_to_html_and_truncates():
    payload = {
        "mimeType": "text/html",
        "body": {"data": b64("<p>" + "a" * 50 + "</p>")},
    }
    result = utils.extract_body(payload, limit=10)
    assert result.startswith("a" * 10)
    assert result.endswith("[truncated]")


def test_list_attachments():
    payload = {
        "parts": [
            {
                "filename": "cv.pdf",
                "mimeType": "application/pdf",
                "body": {"attachmentId": "abc", "size": 10},
            },
            {"filename": "", "mimeType": "text/plain", "body": {"data": "x"}},
        ]
    }
    found = utils.list_attachments(payload)
    assert len(found) == 1 and found[0]["attachmentId"] == "abc"


def test_validate_addresses():
    assert (
        utils.validate_addresses("a@b.com, Name <c@d.org>") == "a@b.com, Name <c@d.org>"
    )
    with pytest.raises(ValueError):
        utils.validate_addresses("not-an-email")
    with pytest.raises(ValueError):
        utils.validate_addresses("a@b.com\nBcc: evil@x.com")
    with pytest.raises(ValueError):
        utils.validate_addresses("")


def test_resolve_attachment_blocks_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "RESUME_DIR", tmp_path.resolve())
    (tmp_path / "resume.pdf").write_bytes(b"%PDF-1.4")

    assert utils.resolve_attachment("resume.pdf").name == "resume.pdf"
    assert utils.resolve_attachment("some/folder/resume.pdf").name == "resume.pdf"
    with pytest.raises(ValueError):
        utils.resolve_attachment("../../etc/passwd")
    with pytest.raises(ValueError):
        utils.resolve_attachment("missing.pdf")


def test_build_mime_with_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "RESUME_DIR", tmp_path.resolve())
    (tmp_path / "resume.pdf").write_bytes(b"%PDF-1.4 fake")

    raw = utils.build_mime(
        "hr@example.com", "Hello", "Body text", attachments=["resume.pdf"]
    )
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw))

    assert msg["To"] == "hr@example.com"
    assert msg["Subject"] == "Hello"
    filenames = [part.get_filename() for part in msg.walk() if part.get_filename()]
    assert filenames == ["resume.pdf"]


def test_build_mime_rejects_header_injection():
    with pytest.raises(ValueError):
        utils.build_mime("a@b.com", "Hi\nBcc: x@y.com", "body")
