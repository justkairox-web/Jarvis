"""Anthropic Messages API client.

The agent works with OpenAI-style messages internally; this class converts them
to Anthropic's format and converts the reply back, so agent.py stays simple."""
import json
import os

import requests

URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-5-5"  # cheap + supports tools; set JARVIS_MODEL to change


class AnthropicLLM:
    def __init__(self, api_key=None, model=None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        key = (key or "").strip().strip("\"'")
        if not key or key == "your-key-here":
            raise RuntimeError("No API key found. Put ANTHROPIC_API_KEY=... in .env")
        self.api_key = key
        self.model = model or os.environ.get("JARVIS_MODEL", DEFAULT_MODEL)

    @staticmethod
    def convert(messages):
        """OpenAI-style messages -> (system text, Anthropic messages)."""
        system, out = "", []
        for m in messages:
            role = m["role"]
            if role == "system":
                system += m["content"]
            elif role == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"],
                         "content": m["content"]}
                last = out[-1] if out else None
                if last and last["role"] == "user" and isinstance(last["content"], list) \
                        and last["content"][0].get("type") == "tool_result":
                    last["content"].append(block)  # results of one turn share a message
                else:
                    out.append({"role": "user", "content": [block]})
            elif role == "assistant" and m.get("tool_calls"):
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for c in m["tool_calls"]:
                    blocks.append({
                        "type": "tool_use", "id": c["id"], "name": c["function"]["name"],
                        "input": json.loads(c["function"].get("arguments") or "{}"),
                    })
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": role, "content": m["content"]})
        while out and out[0]["role"] == "assistant":  # API requires a user turn first
            out.pop(0)
        return system, out

    def chat(self, messages, tools=None):
        system, msgs = self.convert(messages)
        body = {"model": self.model, "max_tokens": 1024, "messages": msgs}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {"name": t["function"]["name"],
                 "description": t["function"]["description"],
                 "input_schema": t["function"]["parameters"]}
                for t in tools
            ]
        r = requests.post(
            URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json=body,
            timeout=60,
        )
        r.raise_for_status()

        text, calls = "", []
        for b in r.json()["content"]:
            if b["type"] == "text":
                text += b["text"]
            elif b["type"] == "tool_use":
                calls.append({"id": b["id"], "type": "function",
                              "function": {"name": b["name"],
                                           "arguments": json.dumps(b["input"])}})
        msg = {"role": "assistant", "content": text or None}
        if calls:
            msg["tool_calls"] = calls
        return msg


HINTS = {
    401: "API key rejected - check ANTHROPIC_API_KEY in .env",
    402: "No credit - check billing in console.anthropic.com",
    403: "Key not allowed to use this model",
    404: "Model name not found - check JARVIS_MODEL",
    429: "Rate limited - wait a moment and retry",
}


def describe_http_error(e):
    code = e.response.status_code
    return f"[error {code}] {HINTS.get(code, '')}\n{e.response.text[:300]}".strip()
