"""
Agent loop using Groq's OpenAI-compatible client for tool calling.
"""
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session
from agent.prompts import SYSTEM_PROMPT
from agent.agent_tools import TOOLS, execute_tool
from database.database_models import ConversationSession

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    timeout=30.0,
)

MODEL = "qwen/qwen3.8-27b"

# How long a conversation is kept before it's treated as stale and reset.
# This exists purely to protect the model's context window -- not as an
# access-control mechanism -- so it lives as a plain timestamp on the row,
# not as a token with its own expiry.
SESSION_IDLE_TIMEOUT = timedelta(hours=1)


def _load_or_reset_session(db: Session, user_id) -> ConversationSession:
    """Lock this user's conversation row for the duration of the request,
    creating it on first use or resetting it if it's gone stale.

    The row lock (SELECT ... FOR UPDATE) is what prevents two concurrent
    requests for the same user (double-click, retry, two tabs) from doing a
    read-modify-write race and silently dropping one of the turns: the
    second request blocks here until the first has committed, then it reads
    the now-current state instead of a stale copy.

    Caller is responsible for committing (or rolling back) the transaction
    this lock lives in.
    """
    session_row = (
        db.query(ConversationSession)
        .filter(ConversationSession.user_id == user_id)
        .with_for_update()
        .first()
    )

    now = datetime.now()

    if session_row is None:
        session_row = ConversationSession(
            user_id=user_id,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}],
            started_at=now,
        )
        db.add(session_row)
        db.flush()
    elif now - session_row.started_at > SESSION_IDLE_TIMEOUT:
        session_row.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        session_row.started_at = now

    return session_row


def run_agent(db: Session, user_id, user_message: str, token: str, max_turns: int = 9) -> dict:
    """Run one turn of the agent loop for `user_id`.

    `user_id` identifies whose conversation this is (used only to key the
    stored context). `token` is unrelated to that -- it's the bearer auth
    forwarded to `execute_tool` so tool calls can hit the backend API as
    this user. Keeping these separate means the JWT is never overloaded as
    a conversation key again.
    """
    session_row = _load_or_reset_session(db, user_id)
    messages = list(session_row.messages)
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
                session_row.messages = messages
                db.commit()
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

        session_row.messages = messages  # commit even on max-turns cutoff
        db.commit()
        return {
            "final_response": "I wasn't able to complete this within the allowed steps.",
            "trace": trace,
            "turns_used": max_turns,
            "hit_max_turns": True,
        }

    except Exception:
        db.rollback()
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