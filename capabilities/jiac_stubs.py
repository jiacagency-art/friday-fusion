"""JIAC Internal Stubs — interfaces prontas para a JIAC plugar."""

from __future__ import annotations
import time
from typing import Any
from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


class _BaseStub(CapabilityImpl):
    name = "jiac_stub"
    category = CapabilityCategory.INTERNAL
    description = "JIAC internal stub"

    def health(self) -> bool:
        return False

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        ctx.logger(
            f"[{self.name}] STUB chamado — precisa implementação real da JIAC",
            level="warn",
        )
        return StepResult(
            success=False,
            error=(
                f"Capability '{self.name}' é um STUB. "
                f"A JIAC precisa de implementar o adapter real em "
                f"capabilities/{self.name}.py substituindo este stub. "
                f"Inputs recebidos: {list(inputs.keys())}"
            ),
            metadata={"stub": True, "engine": self.name, "inputs": inputs},
            finished_at=time.time(),
        )

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        return VerificationResult(passed=False, checks=[{
            "name": "stub_not_implemented", "passed": False,
            "note": "JIAC precisa de substituir o stub"
        }])


class JEVAdapter(_BaseStub):
    name = "browser_jev"
    category = CapabilityCategory.BROWSER
    description = "JEV — JIAC browser engine (stub)"


class AgentReachAdapter(_BaseStub):
    name = "business_prospect"
    category = CapabilityCategory.BUSINESS
    description = "Agent-Reach — prospecção e inteligência comercial (stub)"


class RavenAdapter(_BaseStub):
    name = "workflow_orchestrate"
    category = CapabilityCategory.INTERNAL
    description = "Raven — orquestração de workflows complexos (stub)"


class PersonalJarvisAdapter(_BaseStub):
    name = "personal_context"
    category = CapabilityCategory.COMPUTER
    description = "PersonalJarvis — memória pessoal e integrações (stub)"


class NanoMuseAdapter(_BaseStub):
    """nanoMuse — GPL-3.0. NÃO misturar em produto proprietário sem cumprir GPL."""
    name = "personal_assistant"
    category = CapabilityCategory.INTERNAL
    description = "nanoMuse — agente pessoal (GPL-3.0, stub)"


class AndroidEngineAdapter(_BaseStub):
    name = "android_action"
    category = CapabilityCategory.ANDROID
    description = "Android Engine — CUA/ARTEMIS (stub)"


class ComputerEngineAdapter(_BaseStub):
    name = "computer_action"
    category = CapabilityCategory.COMPUTER
    description = "Computer Engine — CUA desktop (stub)"
