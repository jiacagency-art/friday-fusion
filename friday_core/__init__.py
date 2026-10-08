"""JIAC FRIDAY — Core package (v0.3 with REAL engines)."""

from .orchestrator import Friday
from .types import (
    Capability, CapabilityCategory, CapabilityImpl,
    Objective, Plan, Step, StepResult, Task, TaskStatus,
    VerificationResult, RiskLevel, ExecutionContext,
)
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

__all__ = [
    "Friday", "GeminiClient", "GeminiError",
    "FridayScheduler", "SelfImprovementEngine",
    "Capability", "CapabilityCategory", "CapabilityImpl",
    "Objective", "Plan", "Step", "StepResult", "Task", "TaskStatus",
    "VerificationResult", "RiskLevel", "ExecutionContext",
    "CapabilityRegistry", "UniversalRouter", "LLMRouter", "ExecutionEngine",
    "MemorySystem", "Mem0MemorySystem", "MemoryNS", "StateEngine", "parse_objective",
]

__version__ = "0.3.0"
