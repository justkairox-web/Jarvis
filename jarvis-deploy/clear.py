"""Vercel function: POST /api/clear  (deletes the chat history)"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from http.server import BaseHTTPRequestHandler  # noqa: E402

from webapp import handle_clear, send_json  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # read and discard the request body so the connection stays clean
        length = int(self.headers.get("content-length") or 0)
        if length:
            self.rfile.read(length)
        code, body = handle_clear(self.headers)
        send_json(self, code, body)
