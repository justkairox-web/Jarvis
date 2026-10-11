"""The brain: system prompt + memory + tool-calling loop."""
import json

from tools import build_tools

SYSTEM = (
    "You are Jarvis, a personal AI assistant. Be concise and direct. "
    "When the user shares something durable about themselves, their projects or preferences, "
    "save it with the remember tool. Use recall when a question may depend on saved facts. "
    "Use tools instead of guessing the time or doing arithmetic in your head."
)
MAX_STEPS = 5


class Jarvis:
    def __init__(self, llm, memory):
        self.llm = llm
        self.memory = memory
        self.schemas, self.funcs = build_tools(memory)

    def _system(self):
        facts = self.memory.all_facts()
        known = "\n".join(f"- [{f['topic']}] {f['fact']}" for f in facts)
        return SYSTEM + (f"\n\nKnown facts:\n{known}" if known else "")

    def _run_tool(self, call):
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
            result = self.funcs[name](**args)
        except Exception as e:
            result = f"tool error: {e}"
        if not isinstance(result, str):
            result = json.dumps(result)
        return {"role": "tool", "tool_call_id": call["id"], "content": result}

    def respond(self, user_text):
        history = self.memory.recent_messages()
        self.memory.add_message("user", user_text)
        messages = [{"role": "system", "content": self._system()}] + history
        messages.append({"role": "user", "content": user_text})

        for _ in range(MAX_STEPS):
            msg = self.llm.chat(messages, self.schemas)
            calls = msg.get("tool_calls")
            if not calls:
                text = msg.get("content") or ""
                self.memory.add_message("assistant", text)
                return text
            messages.append(msg)
            messages.extend(self._run_tool(c) for c in calls)

        text = "I got stuck in a tool loop; try rephrasing."
        self.memory.add_message("assistant", text)
        return text
