"""
FRIDAY Memory System — REAL com Mem0
====================================
Sistema de memória que usa Mem0 (mem0ai) quando disponível,
com fallback gracioso para SQLite.

Mem0 usa LLM para extrair e recuperar memórias semânticas.
Sem LLM disponível, cai para o MemorySystem SQLite (key-value simples).

A interface é a mesma do MemorySystem — o Orchestrator não precisa de saber
qual backend está a ser usado.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from .memory import MemorySystem, MemoryNS


class Mem0MemorySystem(MemorySystem):
    """
    Memory System com backend Mem0 (semântico) + SQLite (estrutural).

    Mem0 guarda memórias semânticas ("o utilizador gosta de relatórios em PDF")
    que podem ser recuperadas por similaridade.
    SQLite guarda dados estruturados (capabilities, task state, etc.).

    Uso:
        mem = Mem0MemorySystem(db_path="friday.db")
        mem.add_memory("O utilizador pediu pesquisa sobre Angola", user_id="u1")
        results = mem.search_memory("pesquisas anteriores", user_id="u1")
    """

    def __init__(self, db_path: str | Path = "friday_memory.db",
                 mem0_config: Optional[dict] = None):
        super().__init__(db_path)
        self._mem0 = None
        self._mem0_config = mem0_config or {}
        self._init_mem0()

    def _init_mem0(self):
        """Tenta inicializar Mem0. Se falhar, fica None (fallback para SQLite)."""
        try:
            from mem0 import Memory  # type: ignore
            # Config default: usar Gemini se disponível, senão OpenAI
            config = self._build_mem0_config()
            if config is None:
                print("[Mem0] Sem LLM configurado — usando só SQLite")
                return
            self._mem0 = Memory.from_config(config)
            print(f"[Mem0] Inicializado com sucesso")
        except ImportError:
            print("[Mem0] mem0ai não instalado — usando só SQLite")
        except Exception as e:
            print(f"[Mem0] Erro ao inicializar: {e} — usando só SQLite")
            self._mem0 = None

    def _build_mem0_config(self) -> Optional[dict]:
        """Constrói config do Mem0 baseado nas env vars disponíveis."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if not (gemini_key or openai_key):
            return None

        if gemini_key:
            # Mem0 suporta Gemini via LiteLLM
            return {
                "llm": {
                    "provider": "gemini",
                    "config": {
                        "model": "gemini-2.5-flash",
                        "api_key": gemini_key,
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": "/tmp/friday_mem0_qdrant",
                        "collection_name": "friday_memories",
                    },
                },
            }
        else:
            return {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "gpt-4o-mini",
                        "api_key": openai_key,
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": "/tmp/friday_mem0_qdrant",
                        "collection_name": "friday_memories",
                    },
                },
            }

    def is_mem0_active(self) -> bool:
        return self._mem0 is not None

    # ------------------------------------------------------------------ #
    # API Mem0 (semântica)
    # ------------------------------------------------------------------ #

    def add_memory(self, content: str, user_id: str = "default",
                   metadata: Optional[dict] = None) -> dict[str, Any]:
        """
        Adiciona uma memória semântica. Mem0 extrai factos automaticamente.

        Returns:
            dict com: mem0_used (bool), memories_added (int)
        """
        if self._mem0 is None:
            # Fallback: guardar em SQLite como key-value
            key = f"semantic_{int(time.time()*1000)}"
            self.set(MemoryNS.USER, key, {"content": content, "metadata": metadata or {}},
                     scope=user_id)
            return {"mem0_used": False, "memories_added": 1, "fallback": "sqlite"}

        try:
            result = self._mem0.add(content, user_id=user_id, metadata=metadata or {})
            return {"mem0_used": True, "memories_added": len(result.get("results", [])), "raw": result}
        except Exception as e:
            print(f"[Mem0] erro ao adicionar: {e} — fallback SQLite")
            key = f"semantic_{int(time.time()*1000)}"
            self.set(MemoryNS.USER, key, {"content": content, "error": str(e), "metadata": metadata or {}},
                     scope=user_id)
            return {"mem0_used": False, "memories_added": 1, "fallback": "sqlite", "error": str(e)}

    def search_memory(self, query: str, user_id: str = "default",
                      limit: int = 5) -> list[dict[str, Any]]:
        """
        Pesquisa semântica nas memórias. Retorna memories relevantes.

        Returns:
            lista de dicts com: memory, score, metadata
        """
        if self._mem0 is None:
            # Fallback: pesquisar em SQLite memories semânticas
            all_mem = self.list(MemoryNS.USER, scope=user_id, prefix="semantic_")
            results = []
            for scope, items in all_mem.items():
                for key, val in items.items():
                    content = val.get("content", "") if isinstance(val, dict) else str(val)
                    # Simple keyword matching
                    if query.lower() in content.lower():
                        results.append({"memory": content, "score": 1.0, "metadata": val.get("metadata", {})})
            return results[:limit]

        try:
            results = self._mem0.search(query, user_id=user_id, limit=limit)
            return [
                {"memory": r.get("memory", ""), "score": r.get("score", 0),
                 "metadata": r.get("metadata", {})}
                for r in results
            ]
        except Exception as e:
            print(f"[Mem0] erro ao pesquisar: {e}")
            return []

    def get_all_memories(self, user_id: str = "default") -> list[dict[str, Any]]:
        """Lista todas as memórias semânticas de um user."""
        if self._mem0 is None:
            all_mem = self.list(MemoryNS.USER, scope=user_id, prefix="semantic_")
            results = []
            for scope, items in all_mem.items():
                for key, val in items.items():
                    results.append({"memory": val.get("content", ""), "metadata": val.get("metadata", {})})
            return results
        try:
            return self._mem0.get_all(user_id=user_id)
        except Exception as e:
            print(f"[Mem0] erro ao listar: {e}")
            return []
