"""Vercel function: POST /api/chat"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from http.server import BaseHTTPRequestHandler  # noqa: E402

from webapp import handle_chat, send_json  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        code, body = handle_chat(self.headers, self.rfile.read(n))
        send_json(self, code, body)
