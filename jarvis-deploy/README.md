# Jarvis — Phase 1 (text brain)

Text-only assistant with tool-calling and memory, using the Anthropic API.

## Run on your computer
```
pip3 install -r requirements.txt
cp .env.example .env          # put your Anthropic API key in .env
python3 main.py               # terminal chat
python3 web.py                # browser chat at http://localhost:8000
```
Tests: `pip3 install -r requirements-dev.txt && python3 -m pytest -q tests`

## Host on Vercel (from a GitHub repo)
Environment variables to set in Vercel (never commit them):
- `ANTHROPIC_API_KEY` — your Anthropic key
- `JARVIS_PASSWORD` — password the chat page asks for (required on Vercel)
- Upstash Redis store connected to the project (adds the database variables)

## Files
- `memory.py` — SQLite memory (local) and Redis memory (Vercel)
- `tools.py` — tools (time, calculator, remember, recall); add new ones here
- `llm.py` — Anthropic API client (default claude-haiku-5-5; set JARVIS_MODEL to change)
- `agent.py` — system prompt + tool loop (max 5 steps)
- `webapp.py` — request handling + password check, shared by local and Vercel
- `api/chat.py`, `api/history.py` — Vercel functions
- `public/index.html` — the chat page
- `web.py` / `main.py` — local browser / terminal chat

## Not yet (deliberately)
Voice, wake word, smart home. Don't start these until Phase 1 is solid in daily use.
