"""Vercel function: GET /api/history"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from http.server import BaseHTTPRequestHandler  # noqa: E402

from webapp import handle_history, send_json  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        code, body = handle_history(self.headers)
        send_json(self, code, body)
