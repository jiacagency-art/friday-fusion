"""
FRIDAY Orchestrator — Loop central
==================================
O loop central do JIAC FRIDAY usando os 5 engines reais:

1. Recebe objetivo do utilizador
2. Consulta Mem0 — o que já sei sobre isto?
3. OpenHands planeia como executar
4. AutoGen decide quais agentes activar
5. Hermes pesquisa o que for necessário
6. Browser Use navega se for necessário
7. OpenHands executa e verifica resultado
8. Mem0 guarda o que aprendeu
9. Reporta ao utilizador
"""

from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Optional

from .types import Objective, Plan, Task, TaskStatus, RiskLevel, Step, StepResult
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
from .engines import FridayEngines, get_engines, reset_engines

# v1.0 — Permission, Recovery, Fast Execution (JEV), Proactivity,
#        Agent Factory, Capability Discovery, Briefing
from .permissions import PermissionSystem
from .recovery import RecoveryEngine
from .fast_exec import FastExecutor
from .proactivity import ProactivityEngine
from .agent_factory import AgentFactory
from .capability_discovery import CapabilityDiscovery


class Friday:
    """
    O FRIDAY — ponto de entrada único.

    Loop central:
        Input → Mem0 consulta → OpenHands planeia → AutoGen decide →
        Hermes pesquisa → Browser navega → OpenHands executa →
        Mem0 guarda → Report
    """

    def __init__(
        self,
        work_dir: str | Path = "friday_workspace",
        registry: Optional[CapabilityRegistry] = None,
        use_llm: bool = True,
        llm_client: Optional[GeminiClient] = None,
        use_mem0: bool = True,
    ):
        self.work_dir = Path(work_dir).resolve()   # absoluto: verify de artefactos funciona sempre
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Memória: usar Mem0 (semântico) se disponível, senão SQLite
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

        # LLM client
        self.llm_client = llm_client or GeminiClient()
        self.use_llm = use_llm and self.llm_client.is_configured()

        if self.use_llm:
            self.router = LLMRouter(self.registry, client=self.llm_client)
            self._log(f"Router: LLM (Gemini, model={self.llm_client.model})")
        else:
            self.router = UniversalRouter(self.registry)
            self._log("Router: regras (sem LLM configurado)")

        # v1.0 — PERMISSION SYSTEM (visão §29)
        self.permissions = PermissionSystem(work_dir=str(self.work_dir))
        self.permissions.approval_callback = getattr(self, "_approval_hook", None)

        # v1.0 — RECOVERY ENGINE por tipo de erro (visão §21)
        self.recovery_engine = RecoveryEngine(registry=self.registry, logger=self._log)

        # v1.0 — FAST EXECUTION FABRIC (JEV speed) — executor principal
        self.executor = FastExecutor(
            registry=self.registry, memory=self.memory, state=self.state,
            logger=self._log, max_workers=4, step_timeout=180.0,
            permission_check=self._perm_check, recovery_engine=self.recovery_engine,
        )
        # executor legado mantido para compat/resume
        self.legacy_executor = ExecutionEngine(
            registry=self.registry, memory=self.memory,
            state=self.state, logger=self._log,
        )

        self.scheduler = FridayScheduler(friday_instance=self)
        self.self_improvement = SelfImprovementEngine(memory=self.memory, logger=self._log)

        # v1.0 — PROACTIVITY ENGINE (briefing + alertas sem serem pedidos)
        from capabilities.briefing import BriefingCapability  # lazy (anti-circular)
        self.proactivity = ProactivityEngine(
            work_dir=str(self.work_dir), state=self.state,
            registry=self.registry, scheduler=self.scheduler,
            briefing_impl=BriefingCapability(output_dir=self.work_dir / "outputs"),
            logger=self._log,
        )

        # v1.0 — AGENT FACTORY (agentes especializados on-demand)
        self.agent_factory = AgentFactory(self.registry,
                                          llm_client=self.llm_client if self.use_llm else None,
                                          logger=self._log)
        self.agent_factory.create_all_defaults()

        # v1.0 — CAPABILITY DISCOVERY (GitHub como fonte de capacidades)
        self.discovery = CapabilityDiscovery(self.registry, work_dir=str(self.work_dir),
                                             permissions=self.permissions,
                                             logger=self._log)

        self.started_at = time.time()

        # 5 ENGINES REAIS (v0.5: SWE-agent + Hermes + AutoGen + Browser + Letta Memory)
        self.engines = reset_engines(work_dir=str(self.work_dir))
        engines_summary = self.engines.summary()
        self._log(f"Engines: {engines_summary['available_count']}/{engines_summary['total']} disponíveis")

        self._init_system_memory()

    # ------------------------------------------------------------------ #
    # LOOP CENTRAL
    # ------------------------------------------------------------------ #

    def run(self, raw_objective: str, user_id: str = "default") -> Task:
        """
        Loop central do FRIDAY:
        1. Recebe objetivo
        2. Consulta Mem0
        3. Planeia (router + OpenHands)
        4. AutoGen decide agentes
        5. Executa (Hermes research + Browser + OpenHands)
        6. Verifica
        7. Guarda no Mem0
        8. Reporta
        """
        self._log(f"\n{'='*60}")
        self._log(f"FRIDAY recebeu objetivo: {raw_objective!r}")
        self._log(f"{'='*60}")

        # === PASSO 1: PARSE ===
        objective = self._parse_objective(raw_objective, user_id)

        # === PASSO 2: CONSULTA MEM0 ===
        mem0_context = self._consult_mem0(raw_objective, user_id)

        # === PASSO 3: CRIAR TASK + PLAN ===
        task = Task(
            id=f"task_{int(time.time())}_{os.getpid()}",
            objective=objective,
        )
        task.status = TaskStatus.PLANNING

        # Planeamento: router (regras ou LLM) + insight do OpenHands se disponível
        plan = self.router.route(objective)
        task.plan = plan
        self._log(f"[plan] plano com {len(plan.steps)} steps:")
        for i, s in enumerate(plan.steps, 1):
            self._log(f"  {i}. [{s.capability}] {s.description}")

        self.state.save(task)
        self.state.log_event(task.id, "plan_created", {
            "steps": len(plan.steps),
            "mem0_context_used": mem0_context.get("used", False),
        })

        # Guardar contexto do utilizador
        self.memory.set(MemoryNS.USER, "last_objective", raw_objective, scope=user_id)
        self.memory.set(MemoryNS.USER, "last_task_id", task.id, scope=user_id)

        # === PASSO 4-6: EXECUTAR (com AutoGen se aplicável) ===
        task = self._execute_with_engines(task, mem0_context)

        # === PASSO 7: SELF-IMPROVEMENT ===
        try:
            evaluation = self.self_improvement.evaluate_task(task)
            self.state.log_event(task.id, "self_improvement_evaluation", {
                "score": evaluation.get("score", 0),
                "failures": len(evaluation.get("failures", [])),
                "recoveries": len(evaluation.get("recoveries", [])),
            })
        except Exception as e:
            self._log(f"[self-improve] erro: {e}", level="warn")

        # === PASSO 8: GUARDAR NO MEM0 ===
        self._save_to_mem0(task, user_id)

        # === PASSO 9: REPORTAR ===
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

    # ------------------------------------------------------------------ #
    # Passos do loop
    # ------------------------------------------------------------------ #

    def _parse_objective(self, raw: str, user_id: str) -> Objective:
        """PASSO 1: parse do objective."""
        if self.use_llm:
            try:
                objective = parse_objective_llm(raw, user_id=user_id,
                                                client=self.llm_client)
                self._log(f"[parse:LLM] intent={objective.intent} entities={objective.entities}")
                return objective
            except Exception as e:
                self._log(f"[parse:LLM] falhou ({e}), usando regras", level="warn")
        objective = parse_objective_rules(raw, user_id=user_id)
        self._log(f"[parse:regras] intent={objective.intent} entities={objective.entities}")
        return objective

    def _consult_mem0(self, objective: str, user_id: str) -> dict[str, Any]:
        """PASSO 2: consulta Letta Memory — o que já sei sobre isto?"""
        self._log(f"[letta] a consultar memória para: {objective[:60]}...")
        letta_engine = self.engines.letta_memory
        if not letta_engine.health().available:
            self._log("[letta] indisponível — usando SQLite fallback")
            history = self.memory.list(MemoryNS.TASK)
            return {"used": False, "reason": "letta indisponível",
                    "sqlite_history_count": len(history)}

        try:
            result = letta_engine.search(query=objective, user_id=user_id, top_k=5)
            if result.get("success"):
                results = result.get("results", [])
                self._log(f"[letta] {len(results)} memórias relevantes encontradas")
                return {
                    "used": True,
                    "memories": results[:3],
                    "count": len(results),
                }
            else:
                self._log(f"[letta] erro na pesquisa: {result.get('error', '?')}", level="warn")
                return {"used": False, "error": result.get("error")}
        except Exception as e:
            self._log(f"[letta] excepção: {e}", level="warn")
            return {"used": False, "error": str(e)}

    def _execute_with_engines(self, task: Task, mem0_context: dict) -> Task:
        """
        PASSOS 4-6: executar com engines.

        Se o plano envolver múltiplos agentes, usar AutoGen.
        Caso contrário, usar ExecutionEngine normal.
        """
        # Verificar se AutoGen deve ser usado (plano complexo)
        should_use_autogen = (
            task.plan and len(task.plan.steps) >= 3 and
            self.engines.autogen.health().available
        )

        if should_use_autogen:
            self._log("[autogen] plano complexo — usando AutoGen para orquestrar")
            autogen_result = self.engines.autogen.execute(
                task=task.objective.raw,
                agents_config=[
                    {"name": "Researcher",
                     "system_message": "Research the topic. Pass findings to Writer. Reply TERMINATE when done."},
                    {"name": "Writer",
                     "system_message": "Write a final report based on research. Reply TERMINATE when done."},
                ],
            )
            self.state.log_event(task.id, "autogen_execution", {
                "success": autogen_result.get("success", False),
                "agents": autogen_result.get("agents_used", []),
            })
            if autogen_result.get("success"):
                # Criar step que representa o trabalho do AutoGen
                if task.plan:
                    for step in task.plan.steps:
                        step.status = TaskStatus.COMPLETED
                        step.result = StepResult(
                            success=True,
                            output=autogen_result.get("output"),
                            metadata={"engine": "autogen"},
                            finished_at=time.time(),
                        )
                        task.results[step.id] = step.result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    self.state.save(task)
                    return task

        # Execução normal via FastExecutor (JEV speed) com fallback legado
        try:
            task = self.executor.execute(task)
        except Exception as e:
            self._log(f"[fast] executor falhou ({e}) — fallback legado", level="warn")
            task = self.legacy_executor.execute(task)

        # v1.0 — PROACTIVITY pós-missão: alertas automáticos
        try:
            self.proactivity.check()
        except Exception as e:
            self._log(f"[proactive] check falhou: {e}", level="warn")

        return task

    def _save_to_mem0(self, task: Task, user_id: str):
        """PASSO 8: guardar no Letta Memory."""
        letta_engine = self.engines.letta_memory
        if not letta_engine.health().available:
            return

        summary_parts = [f"Task: {task.objective.raw}", f"Status: {task.status.value}"]
        if task.plan:
            for s in task.plan.steps:
                mark = "✓" if s.status == TaskStatus.COMPLETED else "✗"
                summary_parts.append(f"  {mark} {s.capability}: {s.description}")
                if s.result and s.result.error:
                    summary_parts.append(f"    error: {s.result.error[:200]}")

        summary = "\n".join(summary_parts)
        try:
            letta_engine.add(
                content=summary,
                user_id=user_id,
                metadata={
                    "task_id": task.id,
                    "status": task.status.value,
                    "timestamp": time.time(),
                },
            )
            self._log(f"[letta] guardado: task {task.id}")
        except Exception as e:
            self._log(f"[letta] erro ao guardar: {e}", level="warn")

    # ------------------------------------------------------------------ #
    # API pública auxiliar
    # ------------------------------------------------------------------ #

    # ---- v1.0: permission hook usado pelo FastExecutor ----
    def _perm_check(self, action_level: str, capability: str):
        return self.permissions.check(action_level, capability,
                                      requester="fast_executor")

    # ---- v1.0: briefing proactivo ----
    def daily_briefing(self, city: str = "Luanda", refresh: bool = False) -> dict[str, Any]:
        """Briefing do dia: clima + notícias + IA + agenda + tarefas + resumo."""
        return self.proactivity.daily_briefing(city=city, refresh=refresh)

    def alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        """Alertas proactivos gerados pelo FRIDAY."""
        return self.proactivity.list_alerts(limit)

    def proactive_check(self) -> list[dict[str, Any]]:
        """Corre verificação proactiva (tarefas falhadas, gaps, briefing)."""
        return self.proactivity.check(force=True)

    # ---- v1.0: agentes especializados ----
    def create_agent(self, role: str) -> Optional[str]:
        """Cria e regista um agente especializado (researcher, prospector...)."""
        return self.agent_factory.create(role)

    def available_agent_roles(self) -> list[dict[str, str]]:
        return self.agent_factory.list_available_roles()

    # ---- v1.0: GitHub como fonte de capacidades ----
    def discover_repo(self, repo_url: str) -> dict[str, Any]:
        """Descobre um repo GitHub e registra-o como capability TOOL."""
        return self.discovery.discover(repo_url)

    # ---- v1.0: dashboard web ----
    def serve(self, host: str = "127.0.0.1", port: int = 8500):
        """Lança o Dashboard do FRIDAY (interface de cartões/alertas)."""
        from .dashboard import DashboardServer
        server = DashboardServer(self, host=host, port=port)
        server.serve_forever()

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

    def engines_status(self) -> dict[str, Any]:
        """Estado dos 5 engines reais."""
        return self.engines.summary()

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
