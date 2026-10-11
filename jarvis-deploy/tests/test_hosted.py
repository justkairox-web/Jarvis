import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import memory as memory_mod
import webapp
from agent import Jarvis
from memory import Memory, RedisMemory, make_memory


class EchoLLM:
    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "echo: " + messages[-1]["content"]}


class FakeRedis:
    """Just enough of Upstash's REST API: RPUSH, LTRIM, LRANGE."""

    def __init__(self):
        self.lists = {}

    @staticmethod
    def _rng(lst, a, b):
        n = len(lst)
        a = a + n if a < 0 else a
        b = b + n if b < 0 else b
        return lst[max(a, 0): b + 1]

    def post(self, url, headers=None, json=None, timeout=None):
        assert headers["Authorization"] == "Bearer tok"
        cmd, key, *args = json
        lst = self.lists.setdefault(key, [])
        if cmd == "RPUSH":
            lst.append(args[0])
            result = len(lst)
        elif cmd == "LTRIM":
            self.lists[key] = self._rng(lst, int(args[0]), int(args[1]))
            result = "OK"
        elif cmd == "LRANGE":
            result = self._rng(lst, int(args[0]), int(args[1]))
        else:
            raise AssertionError(cmd)

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"result": result}

        return R()


def test_redis_memory(monkeypatch):
    monkeypatch.setattr(memory_mod.requests, "post", FakeRedis().post)
    m = RedisMemory("https://x.upstash.io", "tok")
    for i in range(3):
        m.add_message("user" if i % 2 == 0 else "assistant", f"m{i}")
    assert [x["content"] for x in m.recent_messages(2)] == ["m1", "m2"]
    m.remember("Project", "building Jarvis")
    m.remember("food", "likes tea")
    assert m.recall("jarvis") == [{"topic": "project", "fact": "building Jarvis"}]
    assert m.all_facts()[0]["topic"] == "food"  # newest first


def test_jarvis_runs_on_redis(monkeypatch):
    monkeypatch.setattr(memory_mod.requests, "post", FakeRedis().post)
    j = Jarvis(EchoLLM(), RedisMemory("https://x.upstash.io", "tok"))
    assert j.respond("hi") == "echo: hi"
    assert [m["role"] for m in j.memory.recent_messages()] == ["user", "assistant"]


def test_make_memory_selection(monkeypatch):
    for k in ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
              "KV_REST_API_URL", "KV_REST_API_TOKEN", "VERCEL"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("JARVIS_DB", os.path.join(tempfile.mkdtemp(), "a.db"))
    assert isinstance(make_memory(), Memory)
    monkeypatch.setenv("KV_REST_API_URL", "https://x")
    monkeypatch.setenv("KV_REST_API_TOKEN", "t")
    assert isinstance(make_memory(), RedisMemory)
    monkeypatch.delenv("KV_REST_API_URL")
    monkeypatch.setenv("VERCEL", "1")
    try:
        make_memory()
        assert False, "should refuse sqlite on Vercel"
    except RuntimeError as e:
        assert "database" in str(e).lower()


def _factory():
    return Jarvis(EchoLLM(), Memory(os.path.join(tempfile.mkdtemp(), "h.db")))


def test_password_rules(monkeypatch):
    j = _factory()
    ok = {"Content-Type": "application/json", "X-Jarvis-Password": "secret"}
    body = json.dumps({"message": "yo"}).encode()

    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("JARVIS_PASSWORD", "secret")
    assert webapp.handle_chat(ok, body, lambda: j) == (200, {"reply": "echo: yo"})
    assert webapp.handle_chat({**ok, "X-Jarvis-Password": "nope"}, body, lambda: j)[0] == 401
    assert webapp.handle_chat({"Content-Type": "application/json"}, body, lambda: j)[0] == 401
    assert webapp.handle_history({"x-jarvis-password": "secret"}, lambda: j)[0] == 200
    assert webapp.handle_history({}, lambda: j)[0] == 401

    # On Vercel with no password configured: refuse everything (fail closed)
    monkeypatch.delenv("JARVIS_PASSWORD")
    monkeypatch.setenv("VERCEL", "1")
    assert webapp.handle_chat(ok, body, lambda: j)[0] == 500
    assert webapp.handle_history({}, lambda: j)[0] == 500


def test_vercel_entrypoints(monkeypatch):
    """Run the real api/chat.py and api/history.py handler classes."""
    monkeypatch.setenv("JARVIS_PASSWORD", "secret")
    monkeypatch.setattr(webapp, "_cached", _factory())
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    import chat as chat_fn
    import history as history_fn

    def serve(handler):
        s = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        return s, f"http://127.0.0.1:{s.server_address[1]}"

    hdr = {"Content-Type": "application/json", "X-Jarvis-Password": "secret"}
    s1, u1 = serve(chat_fn.handler)
    s2, u2 = serve(history_fn.handler)
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            u1, json.dumps({"message": "ping"}).encode(), hdr))
        assert json.load(r)["reply"] == "echo: ping"
        r = urllib.request.urlopen(urllib.request.Request(u2, headers=hdr))
        assert len(json.load(r)["messages"]) == 2
        try:
            urllib.request.urlopen(urllib.request.Request(u2))
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 401
    finally:
        s1.shutdown()
        s2.shutdown()
