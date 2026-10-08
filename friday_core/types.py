"""
FRIDAY Core Types
=================
Tipos fundamentais do JIAC FRIDAY.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CapabilityCategory(str, Enum):
    RESEARCH = "research"
    BROWSER = "browser"
    CODING = "coding"
    BUSINESS = "business"
    ANDROID = "android"
    COMPUTER = "computer"
    DOCUMENTS = "documents"
    INTERNAL = "internal"


@dataclass
class Capability:
    name: str
    category: CapabilityCategory
    description: str
    impl: "CapabilityImpl"
    requires_approval: bool = False
    risk: RiskLevel = RiskLevel.NONE
    tags: list[str] = field(default_factory=list)


@dataclass
class Objective:
    raw: str
    normalized: str
    intent: str
    entities: dict[str, Any]
    user_id: str = "default"
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: f"obj_{uuid.uuid4().hex[:8]}")


@dataclass
class Step:
    id: str
    description: str
    capability: str
    inputs: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    result: Optional["StepResult"] = None


@dataclass
class Plan:
    objective_id: str
    steps: list[Step]
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")


@dataclass
class StepResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    @property
    def duration(self) -> float:
        end = self.finished_at or time.time()
        return end - self.started_at


@dataclass
class VerificationResult:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


@dataclass
class Task:
    id: str
    objective: Objective
    plan: Optional[Plan] = None
    status: TaskStatus = TaskStatus.PENDING
    current_step_id: Optional[str] = None
    risk: RiskLevel = RiskLevel.NONE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    results: dict[str, StepResult] = field(default_factory=dict)
    verifications: dict[str, VerificationResult] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)

    def append_log(self, event: str, **extra):
        self.log.append({"ts": time.time(), "event": event, **extra})
        self.updated_at = time.time()


class CapabilityImpl:
    """Interface base que toda capability concreta deve implementar."""

    name: str = "base"
    category: CapabilityCategory = CapabilityCategory.INTERNAL
    description: str = ""

    def execute(self, inputs: dict[str, Any], ctx: "ExecutionContext") -> StepResult:
        raise NotImplementedError

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        return VerificationResult(
            passed=result.success,
            checks=[{"name": "default_success_check", "passed": result.success}],
        )

    def health(self) -> bool:
        return True


@dataclass
class ExecutionContext:
    task: Task
    memory: Any
    state: Any
    logger: Any
    config: dict[str, Any] = field(default_factory=dict)
