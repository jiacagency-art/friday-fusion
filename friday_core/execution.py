"""Execution Engine — executa Plans com retry + verify + recovery."""

from __future__ import annotations
import time
from typing import Any
from .types import (
    ExecutionContext, Plan, Step, StepResult, Task, TaskStatus, VerificationResult,
)
from .registry import CapabilityRegistry
from .memory import MemorySystem
from .state import StateEngine


class ExecutionEngine:
    def __init__(self, registry: CapabilityRegistry, memory: MemorySystem,
                 state: StateEngine, logger: Any = None):
        self.registry = registry
        self.memory = memory
        self.state = state
        self.logger = logger or (lambda msg, level="info": print(f"[{level}] {msg}"))

    def execute(self, task: Task) -> Task:
        if task.plan is None:
            task.append_log("error", reason="no_plan")
            task.status = TaskStatus.FAILED
            return task

        task.status = TaskStatus.EXECUTING
        self.state.save(task)
        self.state.log_event(task.id, "execution_started")

        outputs_by_step: dict[str, Any] = {}

        for step in task.plan.steps:
            blocked = False
            for dep_id in step.depends_on:
                dep_step = next((s for s in task.plan.steps if s.id == dep_id), None)
                if dep_step is None or dep_step.status != TaskStatus.COMPLETED:
                    blocked = True
                    self.logger(
                        f"[exec] step {step.id} bloqueado (dep {dep_id} não completou)",
                        level="warn")
                    break
            if blocked:
                step.status = TaskStatus.FAILED
                continue

            task.current_step_id = step.id
            self.state.save(task)

            resolved_inputs = self._resolve_inputs(step.inputs, outputs_by_step)
            ctx = ExecutionContext(
                task=task, memory=self.memory, state=self.state,
                logger=self.logger, config={},
            )

            result: StepResult | None = None
            verification: VerificationResult | None = None

            while step.attempts < step.max_attempts:
                step.attempts += 1
                self.logger(
                    f"[exec] step={step.id} cap={step.capability} "
                    f"attempt={step.attempts}/{step.max_attempts}")
                self.state.log_event(task.id, "step_attempt", {
                    "step_id": step.id, "capability": step.capability,
                    "attempt": step.attempts,
                })

                cap = self.registry.get(step.capability)
                if cap is None:
                    result = StepResult(
                        success=False,
                        error=f"Capability não registada: {step.capability}",
                        finished_at=time.time(),
                    )
                    break

                try:
                    result = cap.impl.execute(resolved_inputs, ctx)
                except Exception as e:
                    result = StepResult(
                        success=False, error=f"{type(e).__name__}: {e}",
                        finished_at=time.time())

                try:
                    verification = cap.impl.verify(result, resolved_inputs)
                except Exception as e:
                    verification = VerificationResult(
                        passed=False,
                        checks=[{"name": "verify_exception", "passed": False, "error": str(e)}],
                    )

                if verification.passed:
                    step.status = TaskStatus.COMPLETED
                    step.result = result
                    task.results[step.id] = result
                    task.verifications[step.id] = verification
                    outputs_by_step[step.id] = result.output
                    self.logger(f"[exec] step {step.id} ✓ completed")
                    self.state.log_event(task.id, "step_completed", {
                        "step_id": step.id, "duration_s": result.duration})
                    break
                else:
                    self.logger(
                        f"[exec] step {step.id} ✗ verify failed (attempt {step.attempts})",
                        level="warn")
                    if step.attempts < step.max_attempts:
                        time.sleep(1.0 * step.attempts)
                    else:
                        step.status = TaskStatus.FAILED
                        step.result = result
                        task.results[step.id] = result
                        task.verifications[step.id] = verification
                        self.state.log_event(task.id, "step_failed", {
                            "step_id": step.id, "error": result.error,
                            "checks": verification.checks,
                        })

            self.state.save(task)

        all_completed = all(s.status == TaskStatus.COMPLETED for s in task.plan.steps)
        if all_completed:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
        else:
            task.status = TaskStatus.FAILED

        self.state.save(task)
        self.state.log_event(task.id, "execution_finished", {
            "status": task.status.value,
            "completed_steps": sum(1 for s in task.plan.steps
                                   if s.status == TaskStatus.COMPLETED),
            "total_steps": len(task.plan.steps),
        })
        return task

    def _resolve_inputs(self, inputs: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
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
