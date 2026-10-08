"""
FRIDAY Letta-Style Memory Engine
================================
Implementação local do conceito MemGPT/Letta:
- Core Memory (persona + human) — em SQLite, sempre disponível
- Archival Memory — em ChromaDB (vector search local, sem API keys)
- Recall Memory — conversas recentes em SQLite

Isto substitui o Mem0 (que precisa OPENAI_API_KEY) por uma solução
100% local que funciona com qualquer LLM ou sem LLM.

Baseado no conceito original do MemGPT:
https://github.com/cpacker/MemGPT (branch archive, agora em Letta)
"""

from __future__ import annotations

import os
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class LettaStyleMemory:
    """
    Memória no estilo Letta/MemGPT, 100% local.

    3 camadas de memória:
    1. Core Memory — facts sobre o user e a persona (SQLite)
    2. Archival Memory — conhecimento acumulado (ChromaDB vector search)
    3. Recall Memory — conversas recentes (SQLite)

    Uso:
        mem = LettaStyleMemory(db_path="friday_memory.db")
        mem.add_core("user", "prefers Portuguese")
        mem.add_archival("Sonangol é a empresa petrolífera de Angola")
        results = mem.search_archival("empresas petrolíferas")
    """

    def __init__(self, db_path: str | Path = "friday_letta.db",
                 collection_name: str = "friday_archival"):
        self.db_path = str(db_path)
        self.collection_name = collection_name

        # SQLite para core + recall memory
        import sqlite3
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS core_memory (
                section TEXT NOT NULL,  -- "persona" or "human" or "system"
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (section, key)
            );
            CREATE TABLE IF NOT EXISTS recall_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_recall_created ON recall_memory(created_at);
        """)
        self._conn.commit()

        # ChromaDB para archival memory (vector search local)
        self._chroma_client = None
        self._collection = None
        if CHROMA_AVAILABLE:
            try:
                chroma_path = str(Path(db_path).parent / "chroma")
                self._chroma_client = chromadb.PersistentClient(path=chroma_path)
                self._collection = self._chroma_client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                print(f"[LettaMemory] ChromaDB init falhou: {e}")

    def is_available(self) -> bool:
        """True se pelo menos core memory funciona (sempre True)."""
        return True

    def has_vector_search(self) -> bool:
        """True se archival memory com vector search está disponível."""
        return self._collection is not None

    # ------------------------------------------------------------------ #
    # Core Memory (facts about user/persona)
    # ------------------------------------------------------------------ #

    def add_core(self, section: str, key: str, value: str) -> None:
        """Adiciona/atualiza um fact na core memory."""
        self._conn.execute(
            "INSERT OR REPLACE INTO core_memory (section, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (section, key, value, time.time()),
        )
        self._conn.commit()

    def get_core(self, section: str) -> dict[str, str]:
        """Recupera todos os facts de uma section."""
        rows = self._conn.execute(
            "SELECT key, value FROM core_memory WHERE section=?", (section,),
        ).fetchall()
        return {k: v for k, v in rows}

    def get_core_all(self) -> dict[str, dict[str, str]]:
        """Recupera toda a core memory organizada por section."""
        rows = self._conn.execute(
            "SELECT section, key, value FROM core_memory"
        ).fetchall()
        out: dict[str, dict[str, str]] = {}
        for section, key, value in rows:
            out.setdefault(section, {})[key] = value
        return out

    def delete_core(self, section: str, key: str) -> None:
        self._conn.execute(
            "DELETE FROM core_memory WHERE section=? AND key=?",
            (section, key),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Archival Memory (vector search)
    # ------------------------------------------------------------------ #

    def add_archival(self, content: str, metadata: Optional[dict] = None) -> bool:
        """Adiciona à archival memory (vector search)."""
        if self._collection is None:
            # Fallback: guardar em recall
            self._conn.execute(
                "INSERT INTO recall_memory (role, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                ("archival", content, json.dumps(metadata or {}), time.time()),
            )
            self._conn.commit()
            return False

        try:
            doc_id = hashlib.md5(content.encode()).hexdigest()[:16]
            self._collection.add(
                documents=[content],
                metadatas=[metadata or {}],
                ids=[doc_id],
            )
            return True
        except Exception as e:
            print(f"[LettaMemory] add_archival erro: {e}")
            return False

    def search_archival(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Pesquisa semântica na archival memory."""
        if self._collection is None:
            # Fallback: keyword search em recall
            rows = self._conn.execute(
                "SELECT content, metadata FROM recall_memory WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", n_results),
            ).fetchall()
            return [{"content": c, "metadata": json.loads(m or "{}"), "score": 1.0}
                    for c, m in rows]

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
            )
            out = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                out.append({
                    "content": doc,
                    "metadata": meta or {},
                    "score": 1.0 - dist,  # cosine distance to similarity
                })
            return out
        except Exception as e:
            print(f"[LettaMemory] search_archival erro: {e}")
            return []

    def list_archival(self, limit: int = 100) -> list[dict[str, Any]]:
        """Lista archival memory."""
        if self._collection is None:
            return []
        try:
            results = self._collection.get(limit=limit)
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            ids = results.get("ids", [])
            return [{"id": i, "content": d, "metadata": m}
                    for i, d, m in zip(ids, docs, metas)]
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Recall Memory (conversas recentes)
    # ------------------------------------------------------------------ #

    def add_recall(self, role: str, content: str,
                   metadata: Optional[dict] = None) -> None:
        """Adiciona uma mensagem à recall memory."""
        self._conn.execute(
            "INSERT INTO recall_memory (role, content, metadata, created_at) VALUES (?, ?, ?, ?)",
            (role, content, json.dumps(metadata or {}), time.time()),
        )
        self._conn.commit()

    def get_recall(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recupera as últimas N mensagens."""
        rows = self._conn.execute(
            "SELECT role, content, metadata, created_at FROM recall_memory ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"role": r, "content": c, "metadata": json.loads(m or "{}"),
                 "created_at": t}
                for r, c, m, t in reversed(rows)]

    # ------------------------------------------------------------------ #
    # API de alto nível (compatível com Mem0)
    # ------------------------------------------------------------------ #

    def add(self, content: str, user_id: str = "default",
            metadata: Optional[dict] = None) -> dict[str, Any]:
        """API compatível com Mem0."""
        meta = {"user_id": user_id, **(metadata or {})}
        # Core memory se for um fact curto
        if len(content) < 200 and ("é" in content or "is" in content or "=" in content):
            self.add_core("human", f"fact_{int(time.time()*1000)}", content)
        # Archival sempre
        added = self.add_archival(content, meta)
        # Recall sempre
        self.add_recall("system", content, meta)
        return {"success": True, "archival_added": added}

    def search(self, query: str, user_id: str = "default",
               top_k: int = 5) -> dict[str, Any]:
        """API compatível com Mem0."""
        results = self.search_archival(query, n_results=top_k)
        # Filtrar por user_id se metadata tiver
        if user_id != "default":
            results = [r for r in results
                       if r.get("metadata", {}).get("user_id", "default") == user_id
                       or r.get("metadata", {}).get("user_id") is None]
        return {
            "success": True,
            "results": [{"memory": r["content"], "score": r["score"],
                         "metadata": r["metadata"]}
                        for r in results],
        }

    def get_all(self, user_id: str = "default") -> list[dict[str, Any]]:
        """API compatível com Mem0."""
        items = self.list_archival()
        if user_id != "default":
            items = [i for i in items
                     if i.get("metadata", {}).get("user_id", "default") == user_id
                     or i.get("metadata", {}).get("user_id") is None]
        return items

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def health(self) -> dict[str, Any]:
        return {
            "available": True,
            "vector_search": self.has_vector_search(),
            "core_memory_count": sum(len(v) for v in self.get_core_all().values()),
            "archival_count": len(self.list_archival()) if self._collection else 0,
            "recall_count": self._conn.execute("SELECT COUNT(*) FROM recall_memory").fetchone()[0],
        }

    def close(self):
        self._conn.close()
