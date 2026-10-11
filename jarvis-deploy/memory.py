"""SQLite-backed memory: conversation history + long-term facts."""
import json
import os
import sqlite3
import time

import requests


class Memory:
    def __init__(self, path="jarvis.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                topic TEXT NOT NULL,
                fact TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    # --- conversation history (user/assistant text turns only) ---
    def add_message(self, role, content):
        self.db.execute(
            "INSERT INTO messages (ts, role, content) VALUES (?, ?, ?)",
            (time.time(), role, content),
        )
        self.db.commit()

    def recent_messages(self, limit=20):
        rows = self.db.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # --- long-term facts ---
    def remember(self, topic, fact):
        self.db.execute(
            "INSERT INTO facts (ts, topic, fact) VALUES (?, ?, ?)",
            (time.time(), topic.strip().lower(), fact.strip()),
        )
        self.db.commit()

    def recall(self, query="", limit=10):
        q = f"%{query.strip().lower()}%"
        rows = self.db.execute(
            "SELECT topic, fact FROM facts WHERE topic LIKE ? OR lower(fact) LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (q, q, limit),
        ).fetchall()
        return [{"topic": r["topic"], "fact": r["fact"]} for r in rows]

    def all_facts(self, limit=30):
        return self.recall("", limit)


class RedisMemory:
    """Same interface as Memory, but stored in Upstash Redis (REST API),
    so it keeps working on Vercel where local files do not persist."""

    MAX_ITEMS = 500  # keep only the newest items per list

    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def _cmd(self, *args):
        r = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=list(args),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"Redis error: {data['error']}")
        return data["result"]

    def _push(self, key, item):
        self._cmd("RPUSH", key, json.dumps(item))
        self._cmd("LTRIM", key, str(-self.MAX_ITEMS), "-1")

    def _items(self, key, start, stop):
        return [json.loads(x) for x in (self._cmd("LRANGE", key, str(start), str(stop)) or [])]

    def add_message(self, role, content):
        self._push("jarvis:messages", {"ts": time.time(), "role": role, "content": content})

    def recent_messages(self, limit=20):
        return [{"role": m["role"], "content": m["content"]}
                for m in self._items("jarvis:messages", -limit, -1)]

    def remember(self, topic, fact):
        self._push("jarvis:facts", {"ts": time.time(), "topic": topic.strip().lower(),
                                     "fact": fact.strip()})

    def recall(self, query="", limit=10):
        q = query.strip().lower()
        hits = [f for f in reversed(self._items("jarvis:facts", 0, -1))
                if q in f["topic"] or q in f["fact"].lower()]
        return [{"topic": f["topic"], "fact": f["fact"]} for f in hits[:limit]]

    def all_facts(self, limit=30):
        return self.recall("", limit)


def make_memory():
    """Redis if its settings exist (Vercel), otherwise a local SQLite file."""
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    if url and token:
        return RedisMemory(url, token)
    if os.environ.get("VERCEL"):
        raise RuntimeError("No database connected. In Vercel, add an Upstash Redis store "
                           "to this project (Storage tab) and redeploy.")
    return Memory(os.environ.get("JARVIS_DB", "jarvis.db"))
