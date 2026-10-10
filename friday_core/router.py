"""Universal Router — Objective → Plan (regras; swap-ready para LLM)."""

from __future__ import annotations
import re
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
        # ---- v1.0 intents ----
        elif intent == "video_edit":
            steps = self._plan_video(entities)
        elif intent == "briefing":
            steps = self._plan_briefing(entities)
        elif intent == "data_analyze":
            steps = self._plan_data(entities)
        elif intent == "prospect":
            steps = self._plan_prospect(entities)
        elif intent == "email":
            steps = self._plan_email(entities)
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

    # ====================================================================== #
    # v1.0 planners
    # ====================================================================== #

    def _plan_video(self, entities: dict[str, Any]) -> list[Step]:
        """Editor de vídeo agentivo — pipeline storyboard → corte → formato."""
        raw = entities.get("raw") or entities.get("query") or ""
        source = entities.get("source") or entities.get("quoted") or "video.mp4"
        steps: list[Step] = []
        n = 1

        # storyboard (pré-visualização antes de exportar — visão)
        steps.append(Step(
            id=f"step_{n}", description=f"Storyboard de pré-visualização: {source}",
            capability="video_editor",
            inputs={"action": "storyboard", "source": source, "frames": 12}))
        n += 1

        # corte (se a ordem menciona cortar/duração)
        if re.search(r"corta|corte|cut|segundos|clip", raw, re.IGNORECASE):
            count_m = re.search(r"(\d+)\s*(?:segundos|s\b)", raw, re.IGNORECASE)
            dur = int(count_m.group(1)) if count_m else 30
            steps.append(Step(
                id=f"step_{n}", description=f"Corte de {dur}s do vídeo",
                capability="video_editor",
                inputs={"action": "cut", "source": source,
                        "start": 0, "end": dur},
                depends_on=[steps[0].id]))
            last_id = f"step_{n}"
            n += 1
        else:
            last_id = None
            source_ref = source

        # legendas (se pedido)
        if re.search(r"legend|subt[íi]tulo|caption", raw, re.IGNORECASE):
            steps.append(Step(
                id=f"step_{n}", description="Adicionar legendas PT",
                capability="video_editor",
                inputs={"action": "captions", "source": source,
                        "captions": [{"text": "JIAC FRIDAY", "start": 0.5, "end": 3.5}]},
                depends_on=[]))
            n += 1

        # destaque (círculo)
        if re.search(r"destaca|c[íi]rculo|highlight|produto", raw, re.IGNORECASE):
            steps.append(Step(
                id=f"step_{n}", description="Destacar produto com círculo animado",
                capability="video_editor",
                inputs={"action": "highlight", "source": source,
                        "x": 0.5, "y": 0.45, "radius": 0.16,
                        "start": 0.0, "end": 5.0},
                depends_on=[]))
            n += 1

        # versões verticais/horizontais
        if re.search(r"vertical|tiktok|reels|shorts", raw, re.IGNORECASE):
            steps.append(Step(
                id=f"step_{n}", description="Versão vertical 9:16 (TikTok/Reels)",
                capability="video_editor",
                inputs={"action": "resize", "source": source, "format": "vertical"},
                depends_on=[]))
            n += 1
        if re.search(r"horizontal|youtube", raw, re.IGNORECASE):
            steps.append(Step(
                id=f"step_{n}", description="Versão horizontal 16:9 (YouTube)",
                capability="video_editor",
                inputs={"action": "resize", "source": source, "format": "horizontal"},
                depends_on=[]))
            n += 1

        # se nenhum step específico → só storyboard + info
        if len(steps) == 1:
            steps.append(Step(
                id=f"step_{n}", description="Metadados do vídeo",
                capability="video_editor",
                inputs={"action": "info", "source": source},
                depends_on=[]))

        return steps

    def _plan_briefing(self, entities: dict[str, Any]) -> list[Step]:
        # Briefing é uma capability única que agrega tudo (clima ∥ notícias ∥ agenda)
        # internamente — 1 step rápido (JEV speed).
        return [Step(
            id="step_1", description="Gerar briefing proativo completo",
            capability="briefing",
            inputs={"city": entities.get("city", "Luanda"),
                    "sections": "weather,news,ai,agenda,tasks,summary"},
        )]

    def _plan_data(self, entities: dict[str, Any]) -> list[Step]:
        path = entities.get("path") or entities.get("quoted") or "dados.csv"
        group_by = entities.get("group_by")
        inputs = {"path": path}
        if group_by:
            inputs["group_by"] = group_by
        return [Step(
            id="step_1", description=f"Analisar dataset: {path}",
            capability="data_analyze", inputs=inputs,
        )]

    def _plan_prospect(self, entities: dict[str, Any]) -> list[Step]:
        query = (entities.get("query") or entities.get("quoted") or
                 "empresas Angola que precisam de automação e websites")
        count = int(entities.get("count", 10))
        return [Step(
            id="step_1", description=f"Prospecção comercial: {query}",
            capability="prospect_real",
            inputs={"query": query, "count": count},
        )]

    def _plan_email(self, entities: dict[str, Any]) -> list[Step]:
        to = entities.get("to") or entities.get("email") or ""
        body = entities.get("body") or entities.get("query") or ""
        subject = entities.get("subject") or "Mensagem do FRIDAY"
        return [Step(
            id="step_1", description=f"Email para {to or '(sem destinatário)'}",
            capability="email_send",
            inputs={"to": to, "subject": subject, "body": body},
        )]
