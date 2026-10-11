"""Local browser chat: python3 web.py  ->  http://localhost:8000
Uses the same handlers as the Vercel deployment. Listens on this computer only."""
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from main import load_env
from webapp import get_jarvis, handle_chat, handle_history, send_json

PAGE = Path(__file__).with_name("public") / "index.html"


def make_server(jarvis=None, host="127.0.0.1", port=8000):
    factory = (lambda: jarvis) if jarvis else get_jarvis

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                data = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/api/history":
                send_json(self, *handle_history(self.headers, factory))
            else:
                send_json(self, 404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/chat":
                return send_json(self, 404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", 0))
            send_json(self, *handle_chat(self.headers, self.rfile.read(n), factory))

        def log_message(self, *args):
            pass

    return HTTPServer((host, port), Handler)


def main():
    load_env()
    port = int(os.environ.get("PORT", 8000))
    server = make_server(port=port)
    url = f"http://localhost:{port}"
    print(f"Jarvis chat running at {url}   (press Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
