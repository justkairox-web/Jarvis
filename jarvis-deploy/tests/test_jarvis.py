import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import Jarvis
from memory import Memory


class FakeLLM:
    """Scripted replies; records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools=None):
        self.seen.append(messages)
        return self.script.pop(0)


def call(id_, name, args):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": id_, "type": "function",
                            "function": {"name": name, "arguments": args}}]}


def test_tool_loop_and_persistence():
    path = os.path.join(tempfile.mkdtemp(), "t.db")

    llm = FakeLLM([
        call("1", "remember", '{"topic":"project","fact":"building Jarvis"}'),
        {"role": "assistant", "content": "Noted."},
    ])
    assert Jarvis(llm, Memory(path)).respond("I'm building Jarvis") == "Noted."

    # New process simulation: fresh Memory on the same file
    llm2 = FakeLLM([{"role": "assistant", "content": "You're building Jarvis."}])
    Jarvis(llm2, Memory(path)).respond("what am I building?")
    system = llm2.seen[0][0]["content"]
    assert "building Jarvis" in system                      # fact survived restart
    assert any(m["content"] == "I'm building Jarvis" for m in llm2.seen[0])  # history too


def test_calculator_and_errors():
    mem = Memory(os.path.join(tempfile.mkdtemp(), "t.db"))
    llm = FakeLLM([
        call("1", "calculate", '{"expression":"2**10 + 4"}'),
        call("2", "calculate", '{"expression":"__import__(\'os\')"}'),
        {"role": "assistant", "content": "done"},
    ])
    Jarvis(llm, mem).respond("math")
    tool_msgs = [m for m in llm.seen[-1] if m.get("role") == "tool"]
    assert tool_msgs[0]["content"] == "1028"
    assert tool_msgs[1]["content"].startswith("error")


def test_loop_cap():
    mem = Memory(os.path.join(tempfile.mkdtemp(), "t.db"))
    llm = FakeLLM([call(str(i), "get_time", "{}") for i in range(10)])
    assert "stuck" in Jarvis(llm, mem).respond("loop")


def test_anthropic_message_conversion():
    from llm import AnthropicLLM
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "get_time", "arguments": "{}"}},
            {"id": "b", "type": "function", "function": {"name": "recall", "arguments": '{"query":"x"}'}}]},
        {"role": "tool", "tool_call_id": "a", "content": "noon"},
        {"role": "tool", "tool_call_id": "b", "content": "nothing found"},
    ]
    system, out = AnthropicLLM.convert(msgs)
    assert system == "sys"
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[1]["content"][1]["input"] == {"query": "x"}
    assert len(out[2]["content"]) == 2 and out[2]["content"][0]["type"] == "tool_result"
