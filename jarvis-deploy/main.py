"""Terminal chat: python3 main.py"""
import os

import requests

from agent import Jarvis
from llm import AnthropicLLM, describe_http_error
from memory import make_memory


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    jarvis = Jarvis(AnthropicLLM(), make_memory())
    print("Jarvis online. Type 'exit' to quit.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"exit", "quit"}:
            break
        if not text:
            continue
        try:
            print("jarvis>", jarvis.respond(text))
        except requests.HTTPError as e:
            print(describe_http_error(e))
        except requests.RequestException as e:
            print(f"[network error] {e}")


if __name__ == "__main__":
    main()
