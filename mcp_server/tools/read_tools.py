"""Read-only Gmail tools."""

from config.settings import MAX_BODY_CHARS
from mcp_server.gmail_client import get_service
from mcp_server.utils import (
    UNTRUSTED_NOTE,
    clamp_results,
    extract_body,
    fetch_summaries,
    list_attachments,
    message_summary,
    to_json,
)


def register(mcp) -> None:
    @mcp.tool()
    def get_my_profile() -> str:
        """Return the connected Gmail address and mailbox totals."""
        profile = get_service().users().getProfile(userId="me").execute()
        return to_json(
            {
                "email": profile.get("emailAddress"),
                "messagesTotal": profile.get("messagesTotal"),
                "threadsTotal": profile.get("threadsTotal"),
            }
        )

    @mcp.tool()
    def list_emails(max_results: int = 10, label: str = "INBOX") -> str:
        """List the latest emails in a label (default INBOX).

        Args:
            max_results: How many emails to return (1-50).
            label: Gmail label id, e.g. INBOX, SENT, STARRED, IMPORTANT, SPAM.
        """
        service = get_service()
        resp = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label], maxResults=clamp_results(max_results))
            .execute()
        )
        return to_json(fetch_summaries(service, resp.get("messages", [])))

    @mcp.tool()
    def get_unread_emails(max_results: int = 10) -> str:
        """List unread emails from the inbox (newest first)."""
        service = get_service()
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q="is:unread in:inbox",
                maxResults=clamp_results(max_results),
            )
            .execute()
        )
        return to_json(fetch_summaries(service, resp.get("messages", [])))

    @mcp.tool()
    def search_emails(query: str, max_results: int = 10) -> str:
        """Search emails using Gmail search syntax.

        Examples: 'from:recruiter@x.com', 'subject:interview newer_than:7d',
        'has:attachment is:unread', 'label:starred'.
        """
        service = get_service()
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=clamp_results(max_results))
            .execute()
        )
        return to_json(fetch_summaries(service, resp.get("messages", [])))

    @mcp.tool()
    def read_email(message_id: str) -> str:
        """Read the full content of one email (body is truncated if very long)."""
        msg = (
            get_service()
            .users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        result = message_summary(msg)
        result["body"] = extract_body(msg["payload"])
        result["attachments"] = list_attachments(msg["payload"])
        result["note"] = UNTRUSTED_NOTE
        return to_json(result)

    @mcp.tool()
    def read_thread(thread_id: str) -> str:
        """Read every message in a conversation thread."""
        thread = (
            get_service()
            .users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        messages = []
        for msg in thread.get("messages", []):
            item = message_summary(msg)
            item["body"] = extract_body(msg["payload"], limit=min(3000, MAX_BODY_CHARS))
            messages.append(item)
        return to_json({"note": UNTRUSTED_NOTE, "messages": messages})

    @mcp.tool()
    def thread_has_reply(thread_id: str) -> str:
        """True if someone other than you has written in this thread."""
        thread = (
            get_service()
            .users()
            .threads()
            .get(userId="me", id=thread_id, format="minimal")
            .execute()
        )
        has_reply = any(
            "SENT" not in m.get("labelIds", []) and "DRAFT" not in m.get("labelIds", [])
            for m in thread.get("messages", [])
        )
        return to_json({"thread_id": thread_id, "has_reply": has_reply})
