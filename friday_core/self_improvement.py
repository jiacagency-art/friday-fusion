"""
FRIDAY Self-Improvement Engine
==============================
Sistema de auto-avaliação e melhoria do FRIDAY.

Depois de cada tarefa:
1. Avalia se o resultado foi bom ou mau
2. Se foi mau: analisa porquê
3. Registra a lição aprendida na memória
4. Da próxima vez, aplica a lição

Implementação baseada em regras + heurísticas (não precisa de LLM).
Quando LLM disponível, pode ser extendido para análise semântica.
"""

from __future__ import annotations

import time
import json
from typing import Any, Optional
from .memory import MemorySystem, MemoryNS
from .types import Task, TaskStatus, StepResult, VerificationResult


class SelfImprovementEngine:
    """
    Auto-avaliação e melhoria contínua do FRIDAY.

    Guarda lições aprendidas na memória SYSTEM na namespace "lessons".
    Quando uma capability falha de forma repetida, regista o padrão.
    """

    LESSONS_KEY = "lessons_learned"
    FAILURE_PATTERNS_KEY = "failure_patterns"
    RECOVERY_STRATEGIES_KEY = "recovery_strategies"

    def __init__(self, memory: MemorySystem, logger=None):
        self.memory = memory
        self.logger = logger or (lambda msg, level="info": print(f"[self-improve:{level}] {msg}"))

    def evaluate_task(self, task: Task) -> dict[str, Any]:
        """
        Avalia uma tarefa completada e extrai lições.

        Returns:
            dict com: success, score, lessons, recommendations
        """
        if task.plan is None:
            return {"success": False, "score": 0, "error": "no_plan"}

        total_steps = len(task.plan.steps)
        completed = sum(1 for s in task.plan.steps if s.status == TaskStatus.COMPLETED)
        failed = sum(1 for s in task.plan.steps if s.status == TaskStatus.FAILED)
        total_attempts = sum(s.attempts for s in task.plan.steps)

        # Score: % steps completados - penalização por retries
        base_score = (completed / total_steps * 100) if total_steps > 0 else 0
        retry_penalty = max(0, total_attempts - total_steps) * 5
        score = max(0, base_score - retry_penalty)

        evaluation = {
            "task_id": task.id,
            "objective": task.objective.raw,
            "status": task.status.value,
            "total_steps": total_steps,
            "completed_steps": completed,
            "failed_steps": failed,
            "total_attempts": total_attempts,
            "score": round(score, 1),
            "evaluated_at": time.time(),
        }

        # Identificar padrões de falha
        failures = self._analyze_failures(task)
        if failures:
            evaluation["failures"] = failures
            self._record_lessons(failures, task)

        # Identificar estratégias de recovery bem-sucedidas
        recoveries = self._analyze_recoveries(task)
        if recoveries:
            evaluation["recoveries"] = recoveries
            self._record_recoveries(recoveries, task)

        # Guardar avaliação na memória
        self.memory.set(MemoryNS.TASK, f"eval_{task.id}", evaluation, scope="global")

        self.logger(f"Task {task.id} avaliada: score={score:.1f}/100 "
                    f"({completed}/{total_steps} steps, {failed} falhas)")
        return evaluation

    def _analyze_failures(self, task: Task) -> list[dict[str, Any]]:
        """Analisa steps falhados e extrai padrões."""
        failures = []
        if task.plan is None:
            return failures
        for step in task.plan.steps:
            if step.status != TaskStatus.FAILED:
                continue
            failure = {
                "step_id": step.id,
                "capability": step.capability,
                "description": step.description,
                "error": step.result.error if step.result else "unknown",
                "attempts": step.attempts,
            }
            # Classificar tipo de erro
            error_str = (step.result.error or "").lower() if step.result else ""
            if "timeout" in error_str or "timed out" in error_str:
                failure["error_type"] = "timeout"
                failure["lesson"] = f"Capability '{step.capability}' tende a timeout — considerar aumentar timeout ou reduzir carga"
            elif "not installed" in error_str or "importerror" in error_str:
                failure["error_type"] = "missing_dependency"
                failure["lesson"] = f"Capability '{step.capability}' precisa de dependência não instalada"
            elif "stub" in error_str:
                failure["error_type"] = "stub_not_implemented"
                failure["lesson"] = f"Capability '{step.capability}' é stub — JIAC precisa de implementar"
            elif "quota" in error_str or "429" in error_str:
                failure["error_type"] = "rate_limit"
                failure["lesson"] = f"Rate limit atingido — backoff mais longo ou usar capability alternativa"
            elif "connection" in error_str or "network" in error_str:
                failure["error_type"] = "network"
                failure["lesson"] = f"Problema de rede — retry com backoff exponencial"
            else:
                failure["error_type"] = "unknown"
                failure["lesson"] = f"Erro desconhecido em '{step.capability}': {error_str[:100]}"
            failures.append(failure)
        return failures

    def _analyze_recoveries(self, task: Task) -> list[dict[str, Any]]:
        """Analisa steps que falharam mas recuperaram (attempts > 1 e completed)."""
        recoveries = []
        if task.plan is None:
            return recoveries
        for step in task.plan.steps:
            if step.status != TaskStatus.COMPLETED or step.attempts <= 1:
                continue
            recovery = {
                "step_id": step.id,
                "capability": step.capability,
                "attempts": step.attempts,
                "description": step.description,
                "strategy": "retry_with_backoff",
            }
            recoveries.append(recovery)
        return recoveries

    def _record_lessons(self, failures: list[dict[str, Any]], task: Task):
        """Regista lições aprendidas na memória SYSTEM."""
        existing = self.memory.get(MemoryNS.SYSTEM, self.LESSONS_KEY, scope="global") or []
        for f in failures:
            existing.append({
                "lesson": f["lesson"],
                "capability": f["capability"],
                "error_type": f["error_type"],
                "task_id": task.id,
                "learned_at": time.time(),
            })
        # Manter só as 200 lições mais recentes
        existing = existing[-200:]
        self.memory.set(MemoryNS.SYSTEM, self.LESSONS_KEY, existing, scope="global")
        self.logger(f"Registadas {len(failures)} lições aprendidas")

    def _record_recoveries(self, recoveries: list[dict[str, Any]], task: Task):
        """Regista estratégias de recovery bem-sucedidas."""
        existing = self.memory.get(MemoryNS.SYSTEM, self.RECOVERY_STRATEGIES_KEY, scope="global") or []
        for r in recoveries:
            existing.append({
                "capability": r["capability"],
                "strategy": r["strategy"],
                "attempts_needed": r["attempts"],
                "task_id": task.id,
                "recorded_at": time.time(),
            })
        existing = existing[-200:]
        self.memory.set(MemoryNS.SYSTEM, self.RECOVERY_STRATEGIES_KEY, existing, scope="global")

    def get_lessons(self) -> list[dict[str, Any]]:
        """Recupera todas as lições aprendidas."""
        return self.memory.get(MemoryNS.SYSTEM, self.LESSONS_KEY, scope="global") or []

    def get_recoveries(self) -> list[dict[str, Any]]:
        """Recupera estratégias de recovery bem-sucedidas."""
        return self.memory.get(MemoryNS.SYSTEM, self.RECOVERY_STRATEGIES_KEY, scope="global") or []

    def suggest_for_objective(self, objective_text: str) -> list[str]:
        """
        Sugestões baseadas em lições anteriores para um novo objective.
        Retorna lista de recomendações.
        """
        suggestions = []
        lessons = self.get_lessons()
        # Por agora: se há lições sobre capabilities que o router usaria
        text_lower = objective_text.lower()
        if "pesquisa" in text_lower or "research" in text_lower:
            web_lessons = [l for l in lessons if l.get("capability") == "web_search"]
            if web_lessons:
                suggestions.append(
                    f"Lições anteriores sobre web_search: {len(web_lessons)} falhas registadas. "
                    f"Última: {web_lessons[-1]['lesson']}"
                )
        if not suggestions:
            suggestions.append("Sem lições anteriores relevantes para este objective.")
        return suggestions
