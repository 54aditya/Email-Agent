"""Tools that create or send email. The agent layer asks the human to confirm
send_email / send_draft / reply_to_email before they run."""

from mcp_server.gmail_client import get_service
from mcp_server.utils import (
    build_mime,
    header_map,
    message_summary,
    to_json,
)


def register(mcp) -> None:
    @mcp.tool()
    def send_email(
        to: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        cc: str = "",
        bcc: str = "",
    ) -> str:
        """Send a new email immediately.

        Args:
            to: Recipient address(es), comma separated.
            subject: Subject line (single line).
            body: Plain-text body.
            attachments: File NAMES from list_available_files (e.g. ["my_resume.pdf"]).
            cc: Optional CC address(es).
            bcc: Optional BCC address(es).
        """
        raw = build_mime(to, subject, body, cc=cc, bcc=bcc, attachments=attachments)
        sent = (
            get_service()
            .users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return to_json(
            {
                "status": "sent",
                "id": sent["id"],
                "threadId": sent.get("threadId"),
                "to": to,
                "subject": subject,
                "attachments": attachments or [],
            }
        )

    @mcp.tool()
    def create_draft(
        to: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        cc: str = "",
        bcc: str = "",
    ) -> str:
        """Save an email as a draft without sending it."""
        raw = build_mime(to, subject, body, cc=cc, bcc=bcc, attachments=attachments)
        draft = (
            get_service()
            .users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return to_json(
            {
                "status": "draft_created",
                "draftId": draft["id"],
                "to": to,
                "subject": subject,
            }
        )

    @mcp.tool()
    def list_drafts(max_results: int = 10) -> str:
        """List saved drafts."""
        service = get_service()
        resp = (
            service.users()
            .drafts()
            .list(userId="me", maxResults=max(1, min(max_results, 50)))
            .execute()
        )
        out = []
        for ref in resp.get("drafts", []):
            draft = (
                service.users()
                .drafts()
                .get(userId="me", id=ref["id"], format="metadata")
                .execute()
            )
            item = message_summary(draft["message"])
            item["draftId"] = draft["id"]
            out.append(item)
        return to_json(out)

    @mcp.tool()
    def send_draft(draft_id: str) -> str:
        """Send an existing draft."""
        sent = (
            get_service()
            .users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )
        return to_json(
            {"status": "sent", "id": sent["id"], "threadId": sent.get("threadId")}
        )

    @mcp.tool()
    def reply_to_email(
        message_id: str, body: str, attachments: list[str] | None = None
    ) -> str:
        """Reply (in the same thread) to the sender of an email."""
        service = get_service()
        original = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=[
                    "From",
                    "Reply-To",
                    "Subject",
                    "Message-ID",
                    "References",
                ],
            )
            .execute()
        )
        headers = header_map(original["payload"])
        to = headers.get("reply-to") or headers.get("from", "")
        subject = headers.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        msg_id = headers.get("message-id", "")
        references = f"{headers.get('references', '')} {msg_id}".strip()

        raw = build_mime(
            to,
            subject,
            body,
            attachments=attachments,
            in_reply_to=msg_id or None,
            references=references or None,
        )
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": original["threadId"]})
            .execute()
        )
        return to_json(
            {
                "status": "sent",
                "id": sent["id"],
                "threadId": sent.get("threadId"),
                "to": to,
                "subject": subject,
            }
        )
