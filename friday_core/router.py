"""Universal Router — Objective → Plan (regras; swap-ready para LLM)."""

from __future__ import annotations
from typing import Any
from .types import Objective, Plan, Step
from .registry import CapabilityRegistry


class UniversalRouter:
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def route(self, objective: Objective) -> Plan:
        intent = objective.intent
        entities = objective.entities

        if intent == "research":
            steps = self._plan_research(entities)
        elif intent == "build":
            steps = self._plan_build(entities)
        elif intent == "operate":
            steps = self._plan_operate(entities)
        elif intent == "report":
            steps = self._plan_report(entities)
        else:
            steps = self._plan_research(entities) + self._plan_report(entities)

        validated: list[Step] = []
        for s in steps:
            if self.registry.get(s.capability) is None:
                validated.append(Step(
                    id=s.id,
                    description=f"[MISSING CAPABILITY] {s.description}",
                    capability="__missing__",
                    inputs={"original_capability": s.capability, "reason": "not_registered"},
                    depends_on=s.depends_on,
                ))
            else:
                validated.append(s)

        return Plan(objective_id=objective.id, steps=validated)

    def _plan_research(self, entities: dict[str, Any]) -> list[Step]:
        query = entities.get("query") or entities.get("quoted") or ""
        count = entities.get("count", 10)
        s1 = Step(
            id="step_1",
            description=f"Pesquisar: {query}",
            capability="web_search",
            inputs={"query": query, "max_results": min(count * 2, 30)},
        )
        s2 = Step(
            id="step_2",
            description="Compilar relatório de pesquisa",
            capability="documents_create",
            inputs={
                "path": "research_report.md",
                "format": "markdown",
                "title": f"Relatório de Pesquisa — {query}",
                "content": "{{ step_1.output }}",
                "meta": {"query": query, "engine": "duckduckgo"},
            },
            depends_on=[s1.id],
        )
        return [s1, s2]

    def _plan_build(self, entities: dict[str, Any]) -> list[Step]:
        task_desc = entities.get("query") or ""
        s1 = Step(
            id="step_1",
            description=f"Construir: {task_desc}",
            capability="coding_openhands",
            inputs={"task": task_desc},
        )
        s2 = Step(
            id="step_2",
            description="Documentar entrega",
            capability="documents_create",
            inputs={
                "path": "build_report.md",
                "format": "markdown",
                "title": f"Build Report — {task_desc}",
                "content": "Ver artefactos do coding engine.",
                "meta": {"task": task_desc},
            },
            depends_on=[s1.id],
        )
        return [s1, s2]

    def _plan_operate(self, entities: dict[str, Any]) -> list[Step]:
        task_desc = entities.get("query") or ""
        s1 = Step(
            id="step_1",
            description=f"Operar: {task_desc}",
            capability="browser_use",
            inputs={"task": task_desc},
        )
        s2 = Step(
            id="step_2",
            description="Gerar relatório de operação",
            capability="documents_create",
            inputs={
                "path": "operation_report.md",
                "format": "markdown",
                "title": f"Operation Report — {task_desc}",
                "content": "{{ step_1.output }}",
            },
            depends_on=[s1.id],
        )
        return [s1, s2]

    def _plan_report(self, entities: dict[str, Any]) -> list[Step]:
        query = entities.get("query") or ""
        s1 = Step(
            id="step_1",
            description=f"Pesquisar dados para relatório: {query}",
            capability="web_search",
            inputs={"query": query, "max_results": 15},
        )
        s2 = Step(
            id="step_2",
            description="Compilar relatório final",
            capability="documents_create",
            inputs={
                "path": "final_report.md",
                "format": "markdown",
                "title": f"Relatório — {query}",
                "content": "{{ step_1.output }}",
                "meta": {"intent": "report"},
            },
            depends_on=[s1.id],
        )
        return [s1, s2]
