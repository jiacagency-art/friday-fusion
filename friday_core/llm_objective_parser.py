"""LLM Objective Parser — NL→Objective via Gemini com fallback para regras."""

from __future__ import annotations
import json
from typing import Any, Optional
from .types import Objective
from .objective_parser import parse as parse_rules
from .llm_client import GeminiClient, GeminiError


_SYSTEM_PROMPT = """És o parser de objectivos do JIAC FRIDAY, um sistema operacional de agentes de IA.

Recebes um pedido do utilizador em linguagem natural (português de Angola) e devolves um JSON com a estrutura operacional.

Formato obrigatório:
{
  "intent": "research" | "build" | "operate" | "report" | "analyze" | "automate",
  "entities": {
    "query": "string — termos de pesquisa/ação extraídos do pedido (sem o verbo de intenção)",
    "quoted": "string | null — qualquer frase entre aspas/«»",
    "count": "int | null — número mencionado",
    "targets": ["companies" | "people" | "market" | "site" | "app" | "crm" | "clients" | "products"],
    "default_capability": "web_search" | "browser_use" | "coding_openhands" | "research_owl" | "documents_create" | "business_prospect"
  },
  "confidence": 0.0-1.0
}

Regras:
- "pesquisa/encontra/descobre" → intent=research, default_capability=web_search
- "cria/desenvolve/constroi/monta" → intent=build, default_capability=coding_openhands
- "entra no/abre o/verifica no sistema" → intent=operate, default_capability=browser_use
- "prepara relatório/gera relatório/lista" → intent=report, default_capability=documents_create
- "analisa/estuda/compara" → intent=analyze, default_capability=web_search
- Para research+report combinado, usa intent=report

Devolve APENAS o JSON. Sem markdown, sem explicações."""


def parse_llm(raw: str, user_id: str = "default",
              client: Optional[GeminiClient] = None,
              fallback_to_rules: bool = True) -> Objective:
    if client is None:
        client = GeminiClient()

    if not client.is_configured():
        return parse_rules(raw, user_id=user_id)

    try:
        result = client.chat_json(
            messages=[{"role": "user", "content": raw}],
            system=_SYSTEM_PROMPT,
            temperature=0.0, max_tokens=512,
        )
        return _build_objective_from_llm(raw, result, user_id)
    except (GeminiError, json.JSONDecodeError, KeyError) as e:
        if fallback_to_rules:
            return parse_rules(raw, user_id=user_id)
        raise


def _build_objective_from_llm(raw: str, parsed: dict[str, Any], user_id: str) -> Objective:
    intent = parsed.get("intent", "research")
    entities = parsed.get("entities", {}) or {}
    entities.setdefault("query", raw.strip())
    entities.setdefault("default_capability", "web_search")
    if isinstance(entities.get("targets"), str):
        entities["targets"] = [entities["targets"]]
    return Objective(
        raw=raw, normalized=raw.strip().lower(),
        intent=intent, entities=entities, user_id=user_id,
    )
