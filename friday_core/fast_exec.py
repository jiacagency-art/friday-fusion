"""
FRIDAY Fast Execution Fabric (JEV Speed)
========================================
Requisito central da visão: "velocidade JEV em todo o FRIDAY".

Como funciona:
1. Os steps de um Plan são agrupados em ondas topológicas (waves):
   - steps sem dependências → onda 1
   - steps que só dependem da onda anterior → onda 2, etc.
2. Steps DENTRO da mesma onda correm EM PARALELO (ThreadPoolExecutor).
3. Cache de respostas: (capability + hash(inputs)) → resultado (TTL configurável).
4. Timeout por step — nenhum step externo trava o FRIDAY.
5. Métricas de latência (p50/p95) para o requisito de desempenho.

Isto mantém a semântica do ExecutionEngine mas acelera planos com
múltiplos steps independentes (ex.: briefing = clima ∥ notícias ∥ agenda).
"""

from __future__ import annotations

import hashlib
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .types import Plan, Step, StepResult, Task, TaskStatus, VerificationResult, ExecutionContext


@dataclass
class ExecMetrics:
    started_at: float = field(default_factory=time.time)
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    cache_hits: int = 0
    parallel_waves: int = 0
    step_latencies: list[float] = field(default_factory=list)

    def percentile(self, p: float) -> float:
        if not self.step_latencies:
            return 0.0
        xs = sorted(self.step_latencies)
        k = max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))
        return xs[k]

    def summary(self) -> dict[str, Any]:
        return {
            "steps_total": self.steps_total,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "cache_hits": self.cache_hits,
            "parallel_waves": self.parallel_waves,
            "wall_seconds": round(time.time() - self.started_at, 3),
            "latency_p50_s": round(self.percentile(50), 3),
            "latency_p95_s": round(self.percentile(95), 3),
        }


class ResponseCache:
    """Cache thread-safe com TTL para resultados de capabilities."""

    def __init__(self, ttl_seconds: float = 900.0, max_entries: int = 256):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(capability: str, inputs: dict[str, Any]) -> str:
        blob = json.dumps({"c": capability, "i": inputs}, sort_keys=True,
                          default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    def get(self, k: str) -> tuple[bool, Any]:
        with self._lock:
            item = self._store.get(k)
            if item is None:
                return False, None
            ts, val = item
            if time.time() - ts > self.ttl:
                self._store.pop(k, None)
                return False, None
            return True, val

    def put(self, k: str, val: Any):
        with self._lock:
            if len(self._store) >= self.max_entries:
                # evict mais antigo
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])
                self._store.pop(oldest[0], None)
            self._store[k] = (time.time(), val)

    def clear(self):
        with self._lock:
            self._store.clear()


def build_waves(plan: Plan) -> list[list[Step]]:
    """
    Agrupa steps em ondas topológicas.
    Onda N contém steps cujas dependências estão todas em ondas < N.
    """
    by_id = {s.id: s for s in plan.steps}
    done: set[str] = set()
    waves: list[list[Step]] = []
    remaining = [s for s in plan.steps]

    while remaining:
        wave = [s for s in remaining
                if all(d in done for d in s.depends_on if d in by_id)]
        if not wave:
            # dependências circulares/quebradas — rejeita o resto
            waves.append(remaining)
            break
        waves.append(wave)
        done.update(s.id for s in wave)
        remaining = [s for s in remaining if s.id not in done]
    return waves


class FastExecutor:
    """
    Executor rápido do FRIDAY. Substitui/complementa o ExecutionEngine
    com paralelismo, cache, timeouts e métricas — mantendo verify + recovery.
    """

    def __init__(
        self,
        registry,
        memory,
        state,
        logger: Any = None,
        max_workers: int = 4,
        step_timeout: float = 180.0,
        cache: Optional[ResponseCache] = None,
        permission_check: Optional[Callable[[str, str], Any]] = None,
        recovery_engine=None,
    ):
        self.registry = registry
        self.memory = memory
        self.state = state
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))
        self.max_workers = max(1, max_workers)
        self.step_timeout = step_timeout
        self.cache = cache or ResponseCache()
        self.permission_check = permission_check      # fn(action, capability) -> decision
        self.recovery = recovery_engine
        self.last_metrics: Optional[ExecMetrics] = None

    # ------------------------------------------------------------------ #
    def execute(self, task: Task) -> Task:
        if task.plan is None:
            task.append_log("error", reason="no_plan")
            task.status = TaskStatus.FAILED
            return task

        task.status = TaskStatus.EXECUTING
        self.state.save(task)
        self.state.log_event(task.id, "fast_execution_started")

        metrics = ExecMetrics(steps_total=len(task.plan.steps))
        outputs_by_step: dict[str, Any] = {}

        waves = build_waves(task.plan)
        metrics.parallel_waves = len(waves)
        if len(waves) > 1:
            self.logger(f"[fast] plano dividido em {len(waves)} ondas paralelas")

        for w_idx, wave in enumerate(waves, 1):
            if all(s.status == TaskStatus.COMPLETED for s in wave) and w_idx > 1:
                continue
            self._run_wave(task, wave, outputs_by_step, metrics, wave_idx=w_idx)
            self.state.save(task)

        all_completed = all(s.status == TaskStatus.COMPLETED for s in task.plan.steps)
        task.status = TaskStatus.COMPLETED if all_completed else TaskStatus.FAILED
        if all_completed:
            task.completed_at = time.time()

        self.last_metrics = metrics
        self.state.log_event(task.id, "fast_execution_finished", {
            "status": task.status.value, **metrics.summary(),
        })
        return task

    # ------------------------------------------------------------------ #
    def _run_wave(self, task: Task, wave: list[Step],
                  outputs: dict[str, Any], metrics: ExecMetrics, wave_idx: int):
        wave_has_dep = any(s.depends_on for s in wave)
        if wave_has_dep:
            # steps dependentes entre si dentro da onda: sequencial
            for step in wave:
                self._run_one(task, step, outputs, metrics)
            return

        if len(wave) == 1:
            self._run_one(task, wave[0], outputs, metrics)
            return

        # PARALELO — a essência do Fast Execution Fabric
        self.logger(f"[fast] onda {wave_idx}: {len(wave)} steps em paralelo "
                    f"({', '.join(s.capability for s in wave)})")
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(wave))) as pool:
            futures = {pool.submit(self._run_one, task, s, outputs, metrics): s for s in wave}
            for fut in as_completed(futures):
                try:
                    fut.result(timeout=self.step_timeout + 30)
                except Exception as e:
                    s = futures[fut]
                    self.logger(f"[fast] onda {wave_idx}: step {s.id} excepção: {e}",
                                level="warn")

    # ------------------------------------------------------------------ #
    def _run_one(self, task: Task, step: Step, outputs: dict[str, Any],
                 metrics: ExecMetrics):
        t0 = time.time()
        blocked = False
        for dep_id in step.depends_on:
            dep = next((s for s in task.plan.steps if s.id == dep_id), None)
            if dep is None or dep.status != TaskStatus.COMPLETED:
                blocked = True
                self.logger(f"[fast] step {step.id} bloqueado (dep {dep_id})",
                            level="warn")
                break
        if blocked:
            step.status = TaskStatus.FAILED
            return

        task.current_step_id = step.id
        resolved_inputs = self._resolve_inputs(step.inputs, outputs)

        # ---- PERMISSIONS (visão §29) ----
        if self.permission_check is not None:
            try:
                cap_meta = self.registry.get(step.capability)
                # nível real da acção concreta (ex.: email draft=prepare, send=critical)
                try:
                    lvl = cap_meta.impl.action_level(resolved_inputs) \
                        if cap_meta is not None else "execute"
                except Exception:
                    lvl = cap_meta.risk.value if cap_meta is not None else "execute"
                decision = self.permission_check(lvl, step.capability)
                if not decision.allowed:
                    self.logger(f"[fast] step {step.id} NEGADO por permissions: "
                                f"{decision.reason}", level="warn")
                    step.status = TaskStatus.FAILED
                    step.result = StepResult(success=False, error=f"permission: {decision.reason}",
                                             finished_at=time.time())
                    task.results[step.id] = step.result
                    metrics.steps_failed += 1
                    return
            except Exception:
                pass  # permission system nunca deve travar execução normal

        # ---- CACHE ----
        ckey = ResponseCache.key(step.capability, resolved_inputs)
        hit, cached = self.cache.get(ckey)
        if hit:
            self.logger(f"[fast] step {step.id} cache hit ✓")
            metrics.cache_hits += 1
            step.status = TaskStatus.COMPLETED
            step.result = cached
            task.results[step.id] = cached
            outputs[step.id] = cached.output
            metrics.step_latencies.append(time.time() - t0)
            metrics.steps_completed += 1
            return

        cap = self.registry.get(step.capability)
        ctx = ExecutionContext(task=task, memory=self.memory, state=self.state,
                               logger=self.logger, config={"fast_mode": True})

        while step.attempts < step.max_attempts:
            step.attempts += 1
            self.state.log_event(task.id, "step_attempt", {
                "step_id": step.id, "capability": step.capability,
                "attempt": step.attempts, "fast": True,
            })

            if cap is None:
                result = StepResult(success=False,
                                    error=f"Capability não registada: {step.capability}",
                                    finished_at=time.time())
                verification = VerificationResult(passed=False,
                                                  checks=[{"name": "missing_cap", "passed": False}])
            else:
                try:
                    result = self._with_timeout(cap, resolved_inputs, ctx)
                except Exception as e:
                    result = StepResult(success=False,
                                        error=f"{type(e).__name__}: {e}",
                                        finished_at=time.time())
                try:
                    verification = cap.impl.verify(result, resolved_inputs)
                except Exception as e:
                    verification = VerificationResult(
                        passed=False,
                        checks=[{"name": "verify_exception", "passed": False,
                                 "error": str(e)}])

            if verification.passed:
                step.status = TaskStatus.COMPLETED
                step.result = result
                task.results[step.id] = result
                task.verifications[step.id] = verification
                outputs[step.id] = result.output
                metrics.steps_completed += 1
                metrics.step_latencies.append(time.time() - t0)
                self.state.log_event(task.id, "step_completed", {
                    "step_id": step.id, "duration_s": round(time.time() - t0, 3)})
                self.cache.put(ckey, result)
                return

            # ---- RECOVERY (visão §21) ----
            self.logger(f"[fast] step {step.id} falhou verify "
                        f"(tentativa {step.attempts}/{step.max_attempts})", level="warn")
            if self.recovery is not None and step.attempts < step.max_attempts:
                plan_rec = self.recovery.plan(step.id, step.capability, step.attempts,
                                              result.error if result else None,
                                              resolved_inputs)
                self.logger(f"[recovery] {plan_rec.note}")
                if plan_rec.strategy == "wait_retry":
                    time.sleep(min(plan_rec.wait_seconds, 60.0))
                elif plan_rec.strategy == "alternate" and plan_rec.alternate_capability:
                    cap = self.registry.get(plan_rec.alternate_capability)
                    step.capability = plan_rec.alternate_capability
                elif plan_rec.strategy == "fix_inputs":
                    if plan_rec.input_adjustments.get("__ensure_dirs__"):
                        for v in resolved_inputs.values():
                            if isinstance(v, str) and ("/" in v or "\\" in v):
                                try:
                                    from pathlib import Path as _P
                                    _P(v).parent.mkdir(parents=True, exist_ok=True)
                                except Exception:
                                    pass
                    if plan_rec.input_adjustments.get("__simplify__"):
                        resolved_inputs = {k: v for k, v in resolved_inputs.items()
                                           if not isinstance(v, (dict, list))}
                    if plan_rec.input_adjustments.get("__degrade_llm__"):
                        # sinaliza para capabilities LLM usarem modo regras
                        ctx.config["degrade_llm"] = True

            if step.attempts >= step.max_attempts:
                step.status = TaskStatus.FAILED
                step.result = result
                task.results[step.id] = result
                task.verifications[step.id] = verification
                metrics.steps_failed += 1
                self.state.log_event(task.id, "step_failed", {
                    "step_id": step.id, "error": result.error if result else None})

    # ------------------------------------------------------------------ #
    def _with_timeout(self, cap, inputs: dict[str, Any],
                      ctx: ExecutionContext) -> StepResult:
        """Aplica timeout por step (protege o FRIDAY de engines travados)."""
        if self.step_timeout and self.step_timeout > 0:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(cap.impl.execute, inputs, ctx)
                try:
                    return fut.result(timeout=self.step_timeout)
                except TimeoutError:
                    return StepResult(success=False,
                                      error=f"timeout após {self.step_timeout}s",
                                      finished_at=time.time())
        return cap.impl.execute(inputs, ctx)

    # ------------------------------------------------------------------ #
    def _resolve_inputs(self, inputs: dict[str, Any],
                        outputs: dict[str, Any]) -> dict[str, Any]:
        resolved = {}
        for k, v in inputs.items():
            if isinstance(v, str) and "{{" in v:
                for step_id, out in outputs.items():
                    placeholder = "{{ " + step_id + ".output }}"
                    if placeholder in v:
                        v = out
                        break
                resolved[k] = v
            else:
                resolved[k] = v
        return resolved
