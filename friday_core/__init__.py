"""JIAC FRIDAY — Core package (v1.0 — Sistema Operacional completo)."""

# NB: .types TEM de ser o primeiro import — capabilities podem ser
# importadas antes do core (evita import circular)
from .types import (
    Capability, CapabilityCategory, CapabilityImpl,
    Objective, Plan, Step, StepResult, Task, TaskStatus,
    VerificationResult, RiskLevel, ExecutionContext,
)

from .orchestrator import Friday
from .registry import CapabilityRegistry
from .router import UniversalRouter
from .llm_router import LLMRouter
from .execution import ExecutionEngine
from .memory import MemorySystem, MemoryNS
from .memory_mem0 import Mem0MemorySystem
from .state import StateEngine
from .objective_parser import parse as parse_objective
from .llm_client import GeminiClient, GeminiError
from .scheduler import FridayScheduler
from .self_improvement import SelfImprovementEngine

# v1.0 — novos sistemas do núcleo
from .permissions import PermissionSystem, PermissionLevel, level_of, at_least
from .recovery import RecoveryEngine, classify_error
from .fast_exec import FastExecutor, ResponseCache, build_waves
from .proactivity import ProactivityEngine
from .agent_factory import AgentFactory
from .capability_discovery import CapabilityDiscovery
from .default_registry import build_default_registry

__all__ = [
    "Friday", "GeminiClient", "GeminiError",
    "FridayScheduler", "SelfImprovementEngine",
    "Capability", "CapabilityCategory", "CapabilityImpl",
    "Objective", "Plan", "Step", "StepResult", "Task", "TaskStatus",
    "VerificationResult", "RiskLevel", "ExecutionContext",
    "CapabilityRegistry", "UniversalRouter", "LLMRouter", "ExecutionEngine",
    "MemorySystem", "Mem0MemorySystem", "MemoryNS", "StateEngine", "parse_objective",
    # v1.0
    "PermissionSystem", "PermissionLevel", "level_of", "at_least",
    "RecoveryEngine", "classify_error",
    "FastExecutor", "ResponseCache", "build_waves", "ProactivityEngine",
    "AgentFactory", "CapabilityDiscovery", "build_default_registry",
]

__version__ = "1.0.0"
