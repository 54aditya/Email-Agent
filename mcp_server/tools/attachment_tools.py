"""Tools for files: what can be attached, and downloading received attachments."""

import base64
from pathlib import Path

from config.settings import DOWNLOAD_DIR, RESUME_DIR
from mcp_server.gmail_client import get_service
from mcp_server.utils import list_attachments, to_json


def register(mcp) -> None:
    @mcp.tool()
    def list_available_files() -> str:
        """List files the agent is allowed to attach (resume folder)."""
        RESUME_DIR.mkdir(parents=True, exist_ok=True)
        files = [
            {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)}
            for p in sorted(RESUME_DIR.iterdir())
            if p.is_file() and not p.name.startswith(".")
        ]
        return to_json({"folder": RESUME_DIR.name, "files": files})

    @mcp.tool()
    def list_email_attachments(message_id: str) -> str:
        """List the attachments of a received email."""
        msg = (
            get_service()
            .users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return to_json(list_attachments(msg["payload"]))

    @mcp.tool()
    def download_attachment(message_id: str, attachment_id: str, filename: str) -> str:
        """Download an attachment of a received email into the downloads folder."""
        att = (
            get_service()
            .users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = att["data"]
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "attachment.bin"
        target = DOWNLOAD_DIR / safe_name
        target.write_bytes(raw)
        return to_json({"status": "saved", "path": str(target), "bytes": len(raw)})
