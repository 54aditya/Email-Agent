"""Optional Streamlit chat UI.

Run from the project root:   streamlit run ui/app.py

Sends are never executed automatically: they are queued and shown with
Approve / Reject buttons.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from agent.agent_loop import Agent, log_if_sent
from agent.confirm import format_preview
from agent.importance import format_ranked, rank_emails
from agent.mcp_connector import MCPConnector
from storage import db
from mcp_server.gmail_client import is_authenticated, get_auth_url, fetch_token_from_code


def queue_confirm(name: str, args: dict):
    st.session_state.pending.append({"name": name, "args": args})
    return False, (
        "NOT SENT YET: the action was queued for the user's approval in the UI. "
        "Tell the user it is waiting for their approval. Do not call it again."
    )


async def run_turn(prompt: str) -> str:
    async with MCPConnector() as conn:
        tools = await conn.get_tools()
        agent = Agent(
            conn,
            tools,
            confirm_fn=queue_confirm,
            messages=st.session_state.history,
            verbose=False,
        )
        reply = await agent.run(prompt)
        st.session_state.history = agent.messages
    return reply


async def run_approved(name: str, args: dict):
    async with MCPConnector() as conn:
        text, is_error = await conn.call_tool(name, args)
    if not is_error:
        log_if_sent(name, args, text)
    return text, is_error


async def fetch_important() -> str:
    async with MCPConnector() as conn:
        text, is_error = await conn.call_tool("get_unread_emails", {"max_results": 30})
    if is_error:
        return f"Error: {text}"
    return format_ranked(rank_emails(json.loads(text), top_n=10))


st.set_page_config(page_title="Email Agent", page_icon="📧")
st.title("📧 Email Agent")

redirect_uri = "http://localhost:8501/"  # Note: Update this to your deployed URL later

if not is_authenticated():
    if "code" in st.query_params:
        with st.spinner("Authenticating..."):
            try:
                fetch_token_from_code(st.query_params["code"], redirect_uri)
                st.success("Successfully logged in!")
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                if st.button("Try again"):
                    st.query_params.clear()
                    st.rerun()
        st.stop()
    else:
        st.warning("You need to log in to Gmail first.")
        url, _ = get_auth_url(redirect_uri)
        st.link_button("Log in with Google", url)
        st.stop()

db.init_db()

for key in ("history", "chat", "pending"):
    st.session_state.setdefault(key, [])

with st.sidebar:
    st.header("Quick actions")
    if st.button("Important unread mails"):
        with st.spinner("Checking inbox..."):
            st.session_state.chat.append(
                ("assistant", "```\n" + asyncio.run(fetch_important()) + "\n```")
            )
        st.rerun()
    if st.button("Clear conversation"):
        st.session_state.history, st.session_state.chat, st.session_state.pending = (
            [],
            [],
            [],
        )
        st.rerun()

for role, text in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(text)

for i, action in enumerate(list(st.session_state.pending)):
    with st.container(border=True):
        st.warning(f"Approval needed: {action['name']}")
        st.code(format_preview(action["name"], action["args"]), language="text")
        col_ok, col_no = st.columns(2)
        if col_ok.button("✅ Approve", key=f"ok{i}"):
            with st.spinner("Executing..."):
                text, is_error = asyncio.run(
                    run_approved(action["name"], action["args"])
                )
            outcome = "failed" if is_error else "done"
            st.session_state.chat.append(
                ("assistant", f"Action {action['name']} {outcome}.\n\n```\n{text}\n```")
            )
            st.session_state.history.append(
                {
                    "role": "user",
                    "content": f"[system note] The queued action {action['name']} was approved and {outcome}. Result: {text}",
                }
            )
            st.session_state.pending.pop(i)
            st.rerun()
        if col_no.button("❌ Reject", key=f"no{i}"):
            st.session_state.history.append(
                {
                    "role": "user",
                    "content": f"[system note] The user rejected the queued action {action['name']}.",
                }
            )
            st.session_state.chat.append(("assistant", f"Rejected {action['name']}."))
            st.session_state.pending.pop(i)
            st.rerun()

if prompt := st.chat_input("Ask about your email, or tell me to send one..."):
    st.session_state.chat.append(("user", prompt))
    with st.spinner("Working..."):
        try:
            reply = asyncio.run(run_turn(prompt))
        except Exception as exc:
            reply = f"Error: {exc}"
    st.session_state.chat.append(("assistant", reply))
    st.rerun()
