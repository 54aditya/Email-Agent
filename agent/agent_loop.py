"""Prompt -> LLM -> tool call -> result -> LLM ... loop."""

import inspect
import json
from typing import Callable

from google import genai
from google.genai import types

from agent.confirm import cli_confirm, needs_confirmation
from agent.mcp_connector import MCPConnector
from agent.prompts import build_system_prompt
from config.settings import GEMINI_API_KEY, MAX_AGENT_STEPS, MODEL
from storage import db

SENT_TOOLS = {"send_email", "reply_to_email"}


def log_if_sent(name: str, args: dict, result_text: str) -> None:
    """Record successful sends so /followups can track replies later."""
    if name not in SENT_TOOLS:
        return
    try:
        data = json.loads(result_text)
    except ValueError:
        return
    if data.get("status") != "sent":
        return
    db.log_sent(
        to=data.get("to") or args.get("to", ""),
        subject=data.get("subject") or args.get("subject", ""),
        message_id=data.get("id"),
        thread_id=data.get("threadId"),
    )


def _short(args: dict, limit: int = 90) -> str:
    text = json.dumps(args, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def build_gemini_tools(mcp_tools: list[dict]) -> list[types.Tool]:
    declarations = []
    for t in mcp_tools:
        schema = t.get("input_schema", {})

        declarations.append(
            types.FunctionDeclaration(
                name=t["name"], description=t.get("description", ""), parameters=schema
            )
        )
    if not declarations:
        return []
    return [types.Tool(function_declarations=declarations)]


class Agent:
    def __init__(
        self,
        connector: MCPConnector,
        tools: list[dict],
        confirm_fn: Callable = cli_confirm,
        messages: list | None = None,
        verbose: bool = True,
    ) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.connector = connector
        self.gemini_tools = build_gemini_tools(tools)
        self.confirm_fn = confirm_fn
        self.messages: list = messages if messages is not None else []
        self.verbose = verbose

    def reset(self) -> None:
        self.messages.clear()

    async def _execute(self, name: str, args: dict) -> tuple[str, bool]:
        if self.verbose:
            print(f"  -> {name}({_short(args)})")

        if needs_confirmation(name):
            decision = self.confirm_fn(name, args)
            if inspect.isawaitable(decision):
                decision = await decision
            approved, message = decision
            if not approved:
                return message, True

        try:
            text, is_error = await self.connector.call_tool(name, args)
        except Exception as exc:
            return f"Tool call failed: {exc}", True

        if not is_error:
            log_if_sent(name, args, text)
        return text, is_error

    async def run(self, user_input: str) -> str:
        self.messages.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
        )

        for _ in range(MAX_AGENT_STEPS):
            response = await self.client.aio.models.generate_content(
                model=MODEL,
                contents=self.messages,
                config=types.GenerateContentConfig(
                    system_instruction=build_system_prompt(),
                    tools=self.gemini_tools,
                ),
            )

            if response.candidates and response.candidates[0].content:
                self.messages.append(response.candidates[0].content)

            function_calls = response.function_calls
            if not function_calls:
                return response.text or ""

            results = []
            for fc in function_calls:
                args = {k: v for k, v in fc.args.items()} if fc.args else {}
                text, is_error = await self._execute(fc.name, args)

                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        resp_dict = parsed
                    else:
                        resp_dict = {"result": parsed}
                except Exception:
                    resp_dict = {"result": text}

                results.append(
                    types.Part.from_function_response(name=fc.name, response=resp_dict)
                )

            self.messages.append(types.Content(role="user", parts=results))

        return "I stopped because I reached the maximum number of steps. Try a more specific request."
