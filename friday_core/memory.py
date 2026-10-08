"""Memory System — USER/COMPANY/TASK/SYSTEM namespaces em SQLite."""

from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class MemorySystem:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS memory (
        namespace     TEXT NOT NULL,
        scope         TEXT NOT NULL,
        key           TEXT NOT NULL,
        value         TEXT NOT NULL,
        created_at    REAL NOT NULL,
        updated_at    REAL NOT NULL,
        ttl           REAL,
        PRIMARY KEY (namespace, scope, key)
    );
    CREATE INDEX IF NOT EXISTS idx_memory_ns ON memory(namespace);
    CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory(scope);
    """

    def __init__(self, db_path: str | Path = "friday_memory.db"):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def set(self, namespace: str, key: str, value: Any,
            scope: str = "global", ttl_seconds: Optional[float] = None) -> None:
        now = time.time()
        ttl = now + ttl_seconds if ttl_seconds else None
        self._conn.execute(
            "INSERT OR REPLACE INTO memory "
            "(namespace, scope, key, value, created_at, updated_at, ttl) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (namespace, scope, key, json.dumps(value, ensure_ascii=False, default=str),
             now, now, ttl),
        )
        self._conn.commit()

    def get(self, namespace: str, key: str, scope: str = "global") -> Optional[Any]:
        row = self._conn.execute(
            "SELECT value, ttl FROM memory WHERE namespace=? AND scope=? AND key=?",
            (namespace, scope, key),
        ).fetchone()
        if row is None:
            return None
        value_json, ttl = row
        if ttl is not None and time.time() > ttl:
            self.delete(namespace, key, scope)
            return None
        return json.loads(value_json)

    def delete(self, namespace: str, key: str, scope: str = "global") -> None:
        self._conn.execute(
            "DELETE FROM memory WHERE namespace=? AND scope=? AND key=?",
            (namespace, scope, key),
        )
        self._conn.commit()

    def list(self, namespace: str, scope: Optional[str] = None,
             prefix: Optional[str] = None) -> dict[str, Any]:
        q = "SELECT scope, key, value FROM memory WHERE namespace=?"
        args: list[Any] = [namespace]
        if scope:
            q += " AND scope=?"
            args.append(scope)
        if prefix:
            q += " AND key LIKE ?"
            args.append(f"{prefix}%")
        rows = self._conn.execute(q, args).fetchall()
        out: dict[str, Any] = {}
        for scope_v, key, value_json in rows:
            out.setdefault(scope_v, {})[key] = json.loads(value_json)
        return out

    def append_history(self, task_id: str, entry: dict[str, Any]) -> None:
        existing = self.get("TASK", f"history_{task_id}", scope="global") or []
        existing.append(entry)
        self.set("TASK", f"history_{task_id}", existing, scope="global")

    def get_history(self, task_id: str) -> list[dict[str, Any]]:
        return self.get("TASK", f"history_{task_id}", scope="global") or []

    def close(self):
        self._conn.close()


class MemoryNS:
    USER = "USER"
    COMPANY = "COMPANY"
    TASK = "TASK"
    SYSTEM = "SYSTEM"
