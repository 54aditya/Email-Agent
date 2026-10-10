"""Terminal chat for the email agent.

Run from the project root:   python -m agent.main
"""

import asyncio
import json

from agent.agent_loop import Agent
from agent.importance import format_ranked, rank_emails
from agent.mcp_connector import MCPConnector
from storage import db

HELP = """Commands:
  /important       show important unread emails (rule-based, no LLM cost)
  /followups [N]   sent mails with no reply after N days (default 5)
  /sent            last 10 emails sent through this agent
  /tools           list available MCP tools
  /reset           clear the conversation memory
  /help            show this help
  /exit            quit
Anything else is sent to the AI agent, e.g.:
  Send a mail to hr@example.com asking for AI Engineer opportunities and attach my resume
  Do I have any important mails today?"""


async def show_important(conn: MCPConnector) -> None:
    text, is_error = await conn.call_tool("get_unread_emails", {"max_results": 30})
    if is_error:
        print(f"Error: {text}")
        return
    print(format_ranked(rank_emails(json.loads(text), top_n=10)))


async def check_followups(conn: MCPConnector, days: int) -> None:
    rows = db.pending_follow_ups(days)
    if not rows:
        print(f"Nothing older than {days} days is waiting for a reply.")
        return
    shown = 0
    for row in rows:
        if not row["thread_id"]:
            continue
        text, is_error = await conn.call_tool(
            "thread_has_reply", {"thread_id": row["thread_id"]}
        )
        if is_error:
            continue
        if json.loads(text).get("has_reply"):
            db.mark_replied(row["id"])
            continue
        shown += 1
        print(f"- {row['sent_at'][:10]}  to {row['to_addr']}  |  {row['subject']}")
    if shown == 0:
        print("Everyone has replied. Nothing to follow up.")


def show_sent() -> None:
    rows = db.recent_sent(10)
    if not rows:
        print("No emails sent through the agent yet.")
    for row in rows:
        status = "replied" if row["replied"] else "no reply yet"
        print(
            f"- {row['sent_at'][:16]}  to {row['to_addr']}  |  {row['subject']}  ({status})"
        )


async def main() -> None:
    db.init_db()
    async with MCPConnector() as conn:
        tools = await conn.get_tools()
        agent = Agent(conn, tools)
        print(f"Email agent ready with {len(tools)} tools. Type /help for commands.\n")

        while True:
            try:
                user = (await asyncio.to_thread(input, "you> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue

            cmd, _, arg = user.partition(" ")
            try:
                if cmd in {"/exit", "/quit"}:
                    break
                elif cmd == "/help":
                    print(HELP)
                elif cmd == "/tools":
                    for tool in tools:
                        print(f"- {tool['name']}")
                elif cmd == "/reset":
                    agent.reset()
                    print("Conversation cleared.")
                elif cmd == "/important":
                    await show_important(conn)
                elif cmd == "/followups":
                    await check_followups(conn, int(arg) if arg.isdigit() else 5)
                elif cmd == "/sent":
                    show_sent()
                else:
                    print("\nagent> " + await agent.run(user) + "\n")
            except Exception as exc:
                print(f"Error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
