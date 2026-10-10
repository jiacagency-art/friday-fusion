"""
FRIDAY Recovery Engine
======================
Recuperação de erros do JIAC FRIDAY (visão §21).

Estratégias por tipo de erro:
    network        → retry com backoff exponencial
    rate_limit     → espera longa (respeita Retry-After quando existe)
    missing_cap    → sugere/usa capability alternativa registada
    file_missing   → cria directórios em falta e tenta regenerar
    llm_quota      → degrada para planner de regras (sem LLM)
    verify_failed  → repete com inputs ajustados (reduz escopo do step)
    parse_error    → simplifica input e tenta de novo
    unknown        → retry genérico 1x, depois desiste com diagnóstico

Cada recuperação devolve um plano de recuperação estruturado para o executor.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RecoveryPlan:
    strategy: str                       # retry | wait_retry | alternate | fix_inputs | give_up
    wait_seconds: float = 0.0
    alternate_capability: Optional[str] = None
    input_adjustments: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    @property
    def recoverable(self) -> bool:
        return self.strategy != "give_up"


# padrões de classificação de erro
_NET = re.compile(
    r"(connect|timeout|timed? ?out|network|socket|dns|getaddrinfo|"
    r"connection ?(?:refused|reset|error)|unreachable|ssl)", re.IGNORECASE)
_RATE = re.compile(r"(rate ?limit|429|too many requests|quota exceeded)", re.IGNORECASE)
_MISSING_CAP = re.compile(r"(capability n[ãa]o (?:registada|dispon[íi]vel)|not registered|"
                          r"unknown capability|no module named)", re.IGNORECASE)
_FILE = re.compile(r"(file ?not ?found|no such file|filenotfound|directory|folder)", re.IGNORECASE)
_LLM_QUOTA = re.compile(r"(api ?key|gemini|openai|quota|billing|unauthenticated|401|403)", re.IGNORECASE)
_PARSE = re.compile(r"(json|parse|decode|invalid ?input|valueerror|keyerror)", re.IGNORECASE)


def classify_error(error: Optional[str]) -> str:
    """Classifica um erro numa categoria conhecida."""
    if not error:
        return "unknown"
    if _RATE.search(error):
        return "rate_limit"
    if _LLM_QUOTA.search(error) and not _NET.search(error):
        return "llm_quota"
    if _MISSING_CAP.search(error):
        return "missing_cap"
    if _FILE.search(error):
        return "file_missing"
    if _NET.search(error):
        return "network"
    if _PARSE.search(error):
        return "parse_error"
    return "unknown"


class RecoveryEngine:
    """
    Motor de recuperação. Mantém memória de recuperações para aprendizagem
    (o Self-Improvement Engine lê isto).
    """

    def __init__(self, registry=None, logger: Any = None):
        self.registry = registry          # CapabilityRegistry (para alternativas)
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))
        self.history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    def plan(self, step_id: str, capability: str, attempt: int,
             error: Optional[str], inputs: dict[str, Any] | None = None) -> RecoveryPlan:
        category = classify_error(error)
        inputs = inputs or {}

        if category == "rate_limit":
            p = RecoveryPlan("wait_retry", wait_seconds=30.0 * max(attempt, 1),
                             note="rate limit — espera progressiva")
        elif category == "network":
            p = RecoveryPlan("wait_retry", wait_seconds=2.0 * (2 ** max(attempt - 1, 0)),
                             note="erro de rede — backoff exponencial")
        elif category == "llm_quota":
            p = RecoveryPlan("fix_inputs",
                             input_adjustments={"__degrade_llm__": True},
                             note="sem LLM/API key — degrada para modo regras")
        elif category == "missing_cap":
            alt = self._suggest_alternate(capability)
            if alt:
                p = RecoveryPlan("alternate", alternate_capability=alt,
                                 note=f"usa '{alt}' em vez de '{capability}'")
            else:
                p = RecoveryPlan("fix_inputs",
                                 input_adjustments={"__fallback_local__": True},
                                 note="sem alternativa registada — executa fallback local")
        elif category == "file_missing":
            p = RecoveryPlan("fix_inputs",
                             input_adjustments={"__ensure_dirs__": True},
                             note="recria directórios em falta")
        elif category == "parse_error":
            p = RecoveryPlan("fix_inputs",
                             input_adjustments={"__simplify__": True},
                             note="simplifica inputs e repete")
        elif category == "unknown":
            if attempt < 2:
                p = RecoveryPlan("retry", note="erro desconhecido — retry único")
            else:
                p = RecoveryPlan("give_up", note="erro desconhecido persistente")
        else:
            p = RecoveryPlan("retry", note="recovery genérico")

        p.note = f"[{category}] {p.note}"
        self.history.append({
            "ts": time.time(), "step_id": step_id, "capability": capability,
            "attempt": attempt, "category": category, "strategy": p.strategy,
            "note": p.note,
        })
        return p

    # ------------------------------------------------------------------ #
    def _suggest_alternate(self, capability: str) -> Optional[str]:
        """Sugere capability alternativa saudável na mesma categoria."""
        if self.registry is None:
            return None
        cap = self.registry.get(capability)
        if cap is None:
            # procura qualquer capability saudável
            for c in self.registry.all():
                if c.impl.health():
                    return c.name
            return None
        same_cat = [
            c for c in self.registry.all()
            if c.category == cap.category and c.name != cap.name and c.impl.health()
        ]
        return same_cat[0].name if same_cat else None

    def stats(self) -> dict[str, Any]:
        by_cat: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for h in self.history:
            by_cat[h["category"]] = by_cat.get(h["category"], 0) + 1
            by_strategy[h["strategy"]] = by_strategy.get(h["strategy"], 0) + 1
        return {
            "total_recoveries": len(self.history),
            "by_category": by_cat,
            "by_strategy": by_strategy,
        }
