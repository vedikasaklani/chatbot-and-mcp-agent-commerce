"""
Agent loop using HF's OpenAI-compatible client for tool calling.

- Tool-calling is a structured feature of the chat.completions API
  The OpenAI client parses response.choices[0].message.tool_calls into proper objects.
- Multi-turn tool loops (call tool -> feed result back -> model responds
  or calls another tool) are the standard OpenAI message format, so any
  guide/example for "openai function calling" applies directly here
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
from agent.prompts import SYSTEM_PROMPT
from models import User
from agent.agent_tools import TOOLS, execute_tool

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],  # Groq API key, not HF
    timeout=30.0,
)

MODEL = "qwen/qwen3.8-27b" # Gr

def run_agent(user_message: str, token: str, max_turns: int = 9) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    trace = []

    try:
        for turn in range(max_turns):
            # Actually pass the full messages list, not a reconstructed string
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,  # <-- use the full history
                tools=TOOLS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if not message.tool_calls:
                return {
                    "final_response": message.content,
                    "trace": trace,
                    "turns_used": turn + 1,
                }

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

                # Build a human-readable summary of what happened
                if name == "search_products":
                    summary = f"Searched for products with: {arguments}\nFound {len(result)} products"
                elif name == "add_to_cart":
                    summary = f"Added {arguments.get('quantity', 1)} unit(s) of product {arguments.get('product_id')} to cart"
                elif name == "create_order":
                    summary = f"Created order with ID {result.get('id')}, total: ₹{result.get('total_amount')}"
                else:
                    summary = f"Executed {name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"{summary}\n\nFull result: {json.dumps(result)}",
                })

        return {
            "final_response": "I wasn't able to complete this within the allowed steps.",
            "trace": trace,
            "turns_used": max_turns,
            "hit_max_turns": True,
        }
    except KeyboardInterrupt:
        return _cancelled_response(trace, len(trace))

def _cancelled_response(trace: list, turns_used: int) -> dict:
    return {
        "final_response": "Agent cancelled. No further actions were taken.",
        "trace": trace,
        "turns_used": turns_used,
        "cancelled": True,
    }
