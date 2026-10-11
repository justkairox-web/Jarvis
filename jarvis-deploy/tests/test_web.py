import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import Jarvis
from memory import Memory
from web import make_server


class EchoLLM:
    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "echo: " + messages[-1]["content"]}


def _start():
    os.environ.pop("JARVIS_PASSWORD", None)
    os.environ.pop("VERCEL", None)
    mem = Memory(os.path.join(tempfile.mkdtemp(), "w.db"))
    server = make_server(Jarvis(EchoLLM(), mem), port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _post(url, payload, ctype="application/json"):
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": ctype})
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        return e


def test_page_chat_history():
    server, base = _start()
    try:
        assert b"<title>Jarvis</title>" in urllib.request.urlopen(base + "/").read()

        r = _post(base + "/api/chat", {"message": "hello"})
        assert json.load(r)["reply"] == "echo: hello"

        hist = json.load(urllib.request.urlopen(base + "/api/history"))["messages"]
        assert [m["role"] for m in hist] == ["user", "assistant"]
    finally:
        server.shutdown()


def test_rejects_non_json_and_empty():
    server, base = _start()
    try:
        assert _post(base + "/api/chat", {"message": "x"}, ctype="text/plain").code == 400
        assert _post(base + "/api/chat", {"message": "   "}).code == 400
    finally:
        server.shutdown()
