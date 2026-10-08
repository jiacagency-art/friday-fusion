"""FRIDAY Orchestrator — ponto de entrada único do JIAC FRIDAY."""

from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Any, Optional

from .types import Objective, Plan, Task, TaskStatus, RiskLevel
from .objective_parser import parse as parse_objective_rules
from .llm_objective_parser import parse_llm as parse_objective_llm
from .router import UniversalRouter
from .llm_router import LLMRouter
from .execution import ExecutionEngine
from .registry import CapabilityRegistry
from .default_registry import build_default_registry
from .memory import MemorySystem, MemoryNS
from .memory_mem0 import Mem0MemorySystem
from .state import StateEngine
from .llm_client import GeminiClient
from .scheduler import FridayScheduler
from .self_improvement import SelfImprovementEngine


class Friday:
    def __init__(
        self,
        work_dir: str | Path = "friday_workspace",
        registry: Optional[CapabilityRegistry] = None,
        use_llm: bool = True,
        llm_client: Optional[GeminiClient] = None,
        use_mem0: bool = True,
    ):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Memory: usar Mem0 (semântico) se disponível, senão SQLite simples
        if use_mem0:
            self.memory = Mem0MemorySystem(self.work_dir / "memory.db")
            self._log(f"Memory: {'Mem0 (semântico)' if self.memory.is_mem0_active() else 'SQLite (fallback)'}")
        else:
            self.memory = MemorySystem(self.work_dir / "memory.db")
            self._log("Memory: SQLite (use_mem0=False)")

        self.state = StateEngine(str(self.work_dir / "state.db"))
        self.registry = registry or build_default_registry(
            output_dir=self.work_dir / "outputs"
        )

        self.llm_client = llm_client or GeminiClient()
        self.use_llm = use_llm and self.llm_client.is_configured()

        if self.use_llm:
            self.router = LLMRouter(self.registry, client=self.llm_client)
            self._log(f"Router: LLM (Gemini, model={self.llm_client.model})")
        else:
            self.router = UniversalRouter(self.registry)
            self._log("Router: regras (sem LLM configurado)")

        self.executor = ExecutionEngine(
            registry=self.registry, memory=self.memory,
            state=self.state, logger=self._log,
        )
        self.scheduler = FridayScheduler(friday_instance=self)
        self.self_improvement = SelfImprovementEngine(memory=self.memory, logger=self._log)
        self._init_system_memory()

    def run(self, raw_objective: str, user_id: str = "default") -> Task:
        self._log(f"\n{'='*60}")
        self._log(f"FRIDAY recebeu objetivo: {raw_objective!r}")
        self._log(f"{'='*60}")

        if self.use_llm:
            try:
                objective = parse_objective_llm(raw_objective, user_id=user_id,
                                                client=self.llm_client)
                self._log(f"[parse:LLM] intent={objective.intent} entities={objective.entities}")
            except Exception as e:
                self._log(f"[parse:LLM] falhou ({e}), usando regras", level="warn")
                objective = parse_objective_rules(raw_objective, user_id=user_id)
                self._log(f"[parse:regras] intent={objective.intent} entities={objective.entities}")
        else:
            objective = parse_objective_rules(raw_objective, user_id=user_id)
            self._log(f"[parse:regras] intent={objective.intent} entities={objective.entities}")

        task = Task(id=f"task_{int(time.time())}_{os.getpid()}", objective=objective)
        task.status = TaskStatus.PLANNING
        plan = self.router.route(objective)
        task.plan = plan
        self._log(f"[route] plano com {len(plan.steps)} steps:")
        for i, s in enumerate(plan.steps, 1):
            self._log(f"  {i}. [{s.capability}] {s.description}")
        self.state.save(task)
        self.state.log_event(task.id, "plan_created", {"steps": len(plan.steps)})

        self.memory.set(MemoryNS.USER, "last_objective", raw_objective, scope=user_id)
        self.memory.set(MemoryNS.USER, "last_task_id", task.id, scope=user_id)

        task = self.executor.execute(task)

        # Self-Improvement: avaliar tarefa e extrair lições
        try:
            evaluation = self.self_improvement.evaluate_task(task)
            self.state.log_event(task.id, "self_improvement_evaluation", {
                "score": evaluation.get("score", 0),
                "failures": len(evaluation.get("failures", [])),
                "recoveries": len(evaluation.get("recoveries", [])),
            })
        except Exception as e:
            self._log(f"[self-improve] erro na avaliação: {e}", level="warn")

        self.memory.set(
            MemoryNS.TASK, task.id, {
                "objective": objective.raw,
                "status": task.status.value,
                "completed_steps": sum(1 for s in plan.steps
                                       if s.status == TaskStatus.COMPLETED),
                "total_steps": len(plan.steps),
                "results": {sid: {"success": r.success, "error": r.error,
                                  "metadata": r.metadata}
                            for sid, r in task.results.items()},
            },
            scope="global",
        )

        self._report(task)
        return task

    def resume(self, task_id: str) -> Optional[Task]:
        task = self.state.load(task_id)
        if task is None:
            self._log(f"Tarefa não encontrada: {task_id}", level="error")
            return None
        self._log(f"Retomando tarefa {task_id} (status={task.status.value})")
        return self.executor.execute(task)

    def status(self, task_id: str) -> Optional[dict[str, Any]]:
        task = self.state.load(task_id)
        if task is None:
            return None
        plan = task.plan
        return {
            "id": task.id,
            "objective": task.objective.raw,
            "status": task.status.value,
            "risk": task.risk.value,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
            "current_step": task.current_step_id,
            "steps": [
                {"id": s.id, "description": s.description,
                 "capability": s.capability, "status": s.status.value,
                 "attempts": s.attempts,
                 "success": s.result.success if s.result else None}
                for s in (plan.steps if plan else [])
            ],
            "events": self.state.get_events(task.id)[-10:],
        }

    def capabilities(self) -> dict[str, Any]:
        return self.registry.summary()

    def _init_system_memory(self):
        for cap in self.registry.all():
            self.memory.set(
                MemoryNS.SYSTEM, f"cap_{cap.name}", {
                    "name": cap.name, "category": cap.category.value,
                    "description": cap.description, "healthy": cap.impl.health(),
                    "risk": cap.risk.value, "requires_approval": cap.requires_approval,
                    "tags": cap.tags,
                },
                scope="global",
            )

    def _log(self, msg: str, level: str = "info"):
        print(f"[FRIDAY:{level}] {msg}")

    def _report(self, task: Task):
        print(f"\n{'─'*60}")
        print(f"  TASK: {task.id}")
        print(f"  OBJECTIVE: {task.objective.raw}")
        print(f"  STATUS: {task.status.value.upper()}")
        if task.plan:
            print(f"  STEPS:")
            for s in task.plan.steps:
                mark = "✓" if s.status == TaskStatus.COMPLETED else (
                       "✗" if s.status == TaskStatus.FAILED else "○")
                print(f"    {mark} [{s.capability}] {s.description}")
                if s.result and s.result.error:
                    print(f"        error: {s.result.error[:120]}")
                elif s.result and s.result.success:
                    if isinstance(s.result.output, list):
                        print(f"        → {len(s.result.output)} items")
                    elif isinstance(s.result.output, dict):
                        if "path" in s.result.output:
                            print(f"        → {s.result.output['path']}")
        print(f"{'─'*60}\n")
