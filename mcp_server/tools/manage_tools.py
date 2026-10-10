"""Tools that change labels / state of existing emails."""

from mcp_server.gmail_client import get_service
from mcp_server.utils import to_json


def _modify(
    message_id: str, add: list | None = None, remove: list | None = None
) -> dict:
    return (
        get_service()
        .users()
        .messages()
        .modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": add or [], "removeLabelIds": remove or []},
        )
        .execute()
    )


def _label_id(name: str, create: bool = False) -> str:
    service = get_service()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].lower() == name.lower() or label["id"] == name:
            return label["id"]
    if not create:
        raise ValueError(f"Label '{name}' not found")
    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    return created["id"]


def register(mcp) -> None:
    @mcp.tool()
    def mark_as_read(message_id: str) -> str:
        """Mark an email as read."""
        _modify(message_id, remove=["UNREAD"])
        return to_json({"status": "ok", "id": message_id, "action": "marked_read"})

    @mcp.tool()
    def mark_as_unread(message_id: str) -> str:
        """Mark an email as unread."""
        _modify(message_id, add=["UNREAD"])
        return to_json({"status": "ok", "id": message_id, "action": "marked_unread"})

    @mcp.tool()
    def archive_email(message_id: str) -> str:
        """Remove an email from the inbox (it stays in All Mail)."""
        _modify(message_id, remove=["INBOX"])
        return to_json({"status": "ok", "id": message_id, "action": "archived"})

    @mcp.tool()
    def star_email(message_id: str) -> str:
        """Star an email."""
        _modify(message_id, add=["STARRED"])
        return to_json({"status": "ok", "id": message_id, "action": "starred"})

    @mcp.tool()
    def unstar_email(message_id: str) -> str:
        """Remove the star from an email."""
        _modify(message_id, remove=["STARRED"])
        return to_json({"status": "ok", "id": message_id, "action": "unstarred"})

    @mcp.tool()
    def list_labels() -> str:
        """List all Gmail labels."""
        labels = (
            get_service().users().labels().list(userId="me").execute().get("labels", [])
        )
        return to_json(
            [{"id": l["id"], "name": l["name"], "type": l.get("type")} for l in labels]
        )

    @mcp.tool()
    def add_label(message_id: str, label_name: str) -> str:
        """Add a label to an email (creates the label if it does not exist)."""
        _modify(message_id, add=[_label_id(label_name, create=True)])
        return to_json(
            {"status": "ok", "id": message_id, "action": f"label_added:{label_name}"}
        )

    @mcp.tool()
    def remove_label(message_id: str, label_name: str) -> str:
        """Remove a label from an email."""
        _modify(message_id, remove=[_label_id(label_name)])
        return to_json(
            {"status": "ok", "id": message_id, "action": f"label_removed:{label_name}"}
        )

    @mcp.tool()
    def trash_email(message_id: str) -> str:
        """Move an email to Trash (recoverable for 30 days). Use only if the user explicitly asks."""
        get_service().users().messages().trash(userId="me", id=message_id).execute()
        return to_json({"status": "ok", "id": message_id, "action": "trashed"})
