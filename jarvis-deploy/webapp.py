"""Request logic shared by the local server (web.py) and the Vercel functions (api/).
Each handler returns (status_code, dict) so it is easy to test."""
import hmac
import json
import os

import requests

from agent import Jarvis
from llm import AnthropicLLM, describe_http_error
from memory import make_memory

_cached = None


def get_jarvis():
    global _cached
    if _cached is None:
        _cached = Jarvis(AnthropicLLM(), make_memory())
    return _cached


def _lower(headers):
    return {k.lower(): v for k, v in headers.items()}


def _auth_error(headers):
    """None if allowed. On Vercel a password is mandatory (fails closed)."""
    expected = os.environ.get("JARVIS_PASSWORD", "")
    if not expected and not os.environ.get("VERCEL"):
        return None  # running locally with no password set
    if not expected:
        return 500, {"error": "Server has no JARVIS_PASSWORD set. Add it in Vercel: "
                              "Settings > Environment Variables, then redeploy."}
    given = _lower(headers).get("x-jarvis-password", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return 401, {"error": "Wrong or missing password."}
    return None


def handle_history(headers, factory=get_jarvis):
    err = _auth_error(headers)
    if err:
        return err
    try:
        return 200, {"messages": factory().memory.recent_messages(50)}
    except RuntimeError as e:
        return 500, {"error": str(e)}
    except requests.RequestException as e:
        return 502, {"error": f"Storage error: {e}"}


def handle_chat(headers, raw_body, factory=get_jarvis):
    err = _auth_error(headers)
    if err:
        return err
    # Requiring JSON stops other websites from posting to this server from a browser.
    if "application/json" not in _lower(headers).get("content-type", ""):
        return 400, {"error": "bad request"}
    try:
        text = json.loads(raw_body)["message"].strip()
    except Exception:
        return 400, {"error": "bad request"}
    if not text:
        return 400, {"error": "empty message"}
    try:
        return 200, {"reply": factory().respond(text)}
    except requests.HTTPError as e:
        return 502, {"error": describe_http_error(e)}
    except requests.RequestException as e:
        return 502, {"error": f"Network error: {e}"}
    except RuntimeError as e:
        return 500, {"error": str(e)}


def send_json(h, code, body):
    data = json.dumps(body).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)
