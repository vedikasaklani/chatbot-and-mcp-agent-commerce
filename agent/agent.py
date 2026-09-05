"""
Agent loop using Groq's OpenAI-compatible client for tool calling.
"""
import os
import json
import time
import logging
from dotenv import load_dotenv
from openai import OpenAI
from agent.prompts import SYSTEM_PROMPT
from agent.agent_tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

load_dotenv()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
    timeout=30.0,
)

MODEL = "Qwen/Qwen3.8-27B:ovhcloud"

SESSION_HISTORY_TTL_SECONDS = 60 * 60 * 2

# This is deliberately keyed by a browser-session id rather than an account or
# JWT. A user opening a new browser session must start a new conversation.
conversation_history: dict[str, tuple[list[dict], float]] = {}


def _discard_expired_histories() -> None:
    """Remove histories left behind when a browser closes unexpectedly."""
    cutoff = time.monotonic() - SESSION_HISTORY_TTL_SECONDS
    expired_ids = [
        session_id
        for session_id, (_, last_used) in conversation_history.items()
        if last_used < cutoff
    ]
    for session_id in expired_ids:
        del conversation_history[session_id]


def clear_conversation(session_id: str) -> None:
    """Forget the in-memory history for one browser session."""
    conversation_history.pop(session_id, None)


def run_agent(user_message: str, token:str, session_id: str, max_turns: int = 10) -> dict:
    _discard_expired_histories()
    history, _ = conversation_history.get(
        session_id, ([{"role": "system", "content": SYSTEM_PROMPT}], time.monotonic())
    )
    messages = list(history)
    messages.append({"role": "user", "content": user_message})

    trace = []

    try:
        for turn in range(max_turns):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if not message.tool_calls:
                messages.append({"role": "assistant", "content": message.content})
                conversation_history[session_id] = (messages, time.monotonic())
                return {
                    "final_response": message.content,
                    "trace": trace,
                    "turns_used": turn + 1,
                }

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                result = execute_tool(name, token, arguments)

                trace.append({
                    "turn": turn + 1,
                    "tool": name,
                    "arguments": arguments,
                    "result": result,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

            conversation_history[session_id] = (messages, time.monotonic())

        return {
            "final_response": "I wasn't able to complete this within the allowed steps.",
            "trace": trace,
            "turns_used": max_turns,
            "hit_max_turns": True,
        }

    except Exception as exc:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) or {}
        rate_limit_headers = {
            name: headers.get(name)
        }
        logger.exception(
            getattr(exc, "status_code", getattr(response, "status_code", None)),
            getattr(exc, "body", None),
            rate_limit_headers,
        )
        return {
            "final_response": "Something went wrong on my end — please try that again.",
            "trace": trace,
            "error": True,
        }

def build_decision_record(trace: list[dict], user_message: str, final_response: str, order_id: int = None) -> dict:
    """Turn the raw tool-call trace into a structured, human-readable audit record."""
    steps = [
        {
            "step": entry["turn"],
            "action": entry["tool"],
            "input": entry["arguments"],
            "outcome": _summarize_outcome(entry["tool"], entry["result"]),
        }
        for entry in trace
    ]

    return {
        "order_id": order_id,
        "user_request": user_message,
        "steps": steps,
        "constraints_applied": _extract_constraints(trace),
        "final_response": final_response,
    }


def _summarize_outcome(tool_name: str, result) -> str:
    if tool_name == "search_products":
        return f"Found {len(result)} matching product(s)"
    if tool_name == "add_to_cart":
        return "Item added to cart"
    if tool_name == "create_order":
        if isinstance(result, dict) and "id" in result:
            return f"Order #{result['id']} created, total ₹{result.get('total_amount')}"
        return f"Order creation failed: {result}"
    if tool_name == "get_reviews":
        return f"Retrieved {len(result)} review(s)"
    return "Executed"


def _extract_constraints(trace: list[dict]) -> list[str]:
    """Surface the moments hard rule"""
    notes = []
    for entry in trace:
        if entry["tool"] == "create_order":
            result = entry["result"]
            if isinstance(result, dict) and "exceeds max allowed" in str(result.get("detail", "")):
                notes.append(f"Order blocked by cap: {result['detail']}")
    return notes
