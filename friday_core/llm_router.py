"""LLM Router — Objective→Plan via Gemini com fallback para regras."""

from __future__ import annotations
import json
from typing import Any, Optional
from .types import Objective, Plan, Step
from .router import UniversalRouter
from .llm_client import GeminiClient, GeminiError


_SYSTEM_PROMPT = """És o Universal Router do JIAC FRIDAY — decides que capacidades usar para cumprir um objectivo.

Recebes:
1. O objectivo do utilizador (já parsed)
2. A lista de capacidades disponíveis (algumas podem estar marcadas healthy=false)

Deves devolver um plano JSON:
{
  "steps": [
    {
      "description": "descrição clara do que este passo faz",
      "capability": "nome_exacto_da_capability",
      "inputs": {"chave": "valor"},
      "depends_on": [] | ["step_1"]
    }
  ],
  "rationale": "explicação curta"
}

REGRAS:
- Usa SEMPRE os nomes exactos das capabilities listadas
- NÃO uses capabilities com healthy=false a não ser que não haja alternativa
- Os step IDs devem ser "step_1", "step_2", etc.
- Para传递 resultados entre steps, usa "{{ step_N.output }}" no inputs
- Mantém o plano minimalista
- Para research: web_search (rápido, sem chave)
- Para documents: documents_create com path, format, title, content, meta
- Para browser: browser_use com task description
- Para coding: coding_openhands com task description

Devolve APENAS o JSON."""


class LLMRouter(UniversalRouter):
    def __init__(self, registry, client: Optional[GeminiClient] = None,
                 fallback_to_rules: bool = True):
        super().__init__(registry)
        self.client = client or GeminiClient()
        self.fallback_to_rules = fallback_to_rules

    def route(self, objective: Objective) -> Plan:
        if not self.client.is_configured():
            return super().route(objective)
        try:
            return self._route_with_llm(objective)
        except (GeminiError, json.JSONDecodeError, KeyError, ValueError) as e:
            if self.fallback_to_rules:
                print(f"[LLMRouter] fallback para regras: {type(e).__name__}: {e}")
                return super().route(objective)
            raise

    def _route_with_llm(self, objective: Objective) -> Plan:
        caps_desc = self._describe_capabilities()
        user_msg = f"""OBJECTIVE:
- raw: {objective.raw}
- intent: {objective.intent}
- entities: {json.dumps(objective.entities, ensure_ascii=False)}

AVAILABLE CAPABILITIES:
{caps_desc}

Gera o plano JSON."""
        result = self.client.chat_json(
            messages=[{"role": "user", "content": user_msg}],
            system=_SYSTEM_PROMPT,
            temperature=0.1, max_tokens=2048,
        )
        return self._build_plan_from_llm(result, objective)

    def _describe_capabilities(self) -> str:
        lines = []
        for cap in self.registry.all():
            healthy = cap.impl.health()
            tag = "✓" if healthy else "✗"
            lines.append(f"- {tag} {cap.name} [{cap.category.value}]: {cap.description}")
        return "\n".join(lines)

    def _build_plan_from_llm(self, parsed: dict[str, Any], objective: Objective) -> Plan:
        steps_data = parsed.get("steps", [])
        if not steps_data:
            raise ValueError("LLM devolveu plano vazio")

        steps: list[Step] = []
        for i, sd in enumerate(steps_data, 1):
            step_id = sd.get("id") or f"step_{i}"
            cap_name = sd.get("capability", "")
            if not cap_name or self.registry.get(cap_name) is None:
                steps.append(Step(
                    id=step_id,
                    description=f"[LLM usou capability inválida: {cap_name}] {sd.get('description', '')}",
                    capability="__missing__",
                    inputs={"original_capability": cap_name},
                    depends_on=sd.get("depends_on", []),
                ))
                continue
            steps.append(Step(
                id=step_id,
                description=sd.get("description", ""),
                capability=cap_name,
                inputs=sd.get("inputs", {}),
                depends_on=sd.get("depends_on", []),
            ))
        return Plan(objective_id=objective.id, steps=steps)
