"""Persistent message-id dedupe (SQLite), so restarts and webhook retries never double-reply."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: str, retention_seconds: int = 7 * 24 * 3600):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, at REAL NOT NULL)")
        self._lock = threading.Lock()
        self._retention = retention_seconds
        self.prune()

    def claim(self, message_id: str) -> bool:
        """Atomically mark `message_id` as seen. True only the first time it is seen."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO seen (id, at) VALUES (?, ?)", (message_id, time.time())
            )
            return cur.rowcount == 1

    def prune(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM seen WHERE at < ?", (time.time() - self._retention,))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
