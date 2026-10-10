"""Human-in-the-loop approval for actions that change the outside world."""

SENSITIVE_TOOLS = {"send_email", "send_draft", "reply_to_email", "trash_email"}


def needs_confirmation(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS


def format_preview(tool_name: str, args: dict) -> str:
    lines = [f"Action: {tool_name}"]
    labels = {
        "to": "To",
        "cc": "Cc",
        "bcc": "Bcc",
        "subject": "Subject",
        "message_id": "Message id",
        "draft_id": "Draft id",
    }
    for key, label in labels.items():
        if args.get(key):
            lines.append(f"{label}: {args[key]}")
    if args.get("attachments"):
        lines.append(f"Attachments: {', '.join(args['attachments'])}")
    if args.get("body"):
        lines.append("-" * 50)
        lines.append(args["body"])
        lines.append("-" * 50)
    return "\n".join(lines)


def cli_confirm(tool_name: str, args: dict) -> tuple[bool, str]:
    """Ask in the terminal. Returns (approved, message_for_llm_if_declined)."""
    print("\n" + "=" * 60)
    print(" APPROVAL NEEDED")
    print("=" * 60)
    print(format_preview(tool_name, args))
    print("=" * 60)
    answer = input("Approve? [y/N]: ").strip().lower()
    if answer in {"y", "yes"}:
        return True, ""
    return (
        False,
        "The user DECLINED this action. Do not retry it. Ask what they want changed.",
    )
