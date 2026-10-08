"""External Engine Adapters — wrappers para engines públicos.

Cada adapter faz lazy loading do engine correspondente em engines/.
Quando o engine não está instalado, health()=False e execute() devolve
erro claro com instruções de instalação.
"""

from __future__ import annotations
import os
import time
from typing import Any
from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _not_installed_msg(engine: str, engine_path: str, extra: str = "") -> str:
    msg = (
        f"{engine} não instalado. Para activar:\n"
        f"  pip install -e {engine_path}\n"
    )
    if extra:
        msg += f"  {extra}\n"
    return msg


def _default_verify(result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
    return VerificationResult(
        passed=result.success,
        checks=[{"name": "default", "passed": result.success}],
    )


def _health_check(module_name: str, env_var: str | None = None) -> bool:
    try:
        import importlib
        importlib.import_module(module_name)
        if env_var and not os.environ.get(env_var):
            return False
        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- #
# OWL Adapter
# --------------------------------------------------------------------------- #

class OWLAdapter(CapabilityImpl):
    name = "research_owl"
    category = CapabilityCategory.RESEARCH
    description = "OWL — research agent multi-turno"

    def __init__(self, engine_path: str = "engines/owl"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("owl", "GEMINI_API_KEY") or _health_check("owl", "OPENAI_API_KEY")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task") or inputs.get("query")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[owl] task={task!r}")
        try:
            from owl.agent import OwlAgent  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("OWL", self.engine_path,
                                          "export GEMINI_API_KEY=...") + f"Erro: {e}",
                finished_at=time.time(),
            )
        try:
            agent = OwlAgent(task=task, model=inputs.get("model", "gemini-2.5-flash"))
            result = agent.run()
            return StepResult(
                success=True, output={"answer": str(result), "raw": result},
                metadata={"engine": "owl", "duration_s": round(time.time() - started, 2)},
                finished_at=time.time(),
            )
        except Exception as e:
            return StepResult(success=False, error=f"{type(e).__name__}: {e}",
                              finished_at=time.time())

    verify = _default_verify


# --------------------------------------------------------------------------- #
# OpenHands Adapter
# --------------------------------------------------------------------------- #

class OpenHandsAdapter(CapabilityImpl):
    name = "coding_openhands"
    category = CapabilityCategory.CODING
    description = "OpenHands — agente de engenharia de software"

    def __init__(self, engine_path: str = "engines/openhands"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("openhands")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task") or inputs.get("description")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[openhands] task={task!r}")
        try:
            from openhands.controller.default_controller import DefaultController  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("OpenHands", self.engine_path,
                                          "Docker daemon a correr") + f"Erro: {e}",
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="OpenHands integration requires Docker runtime — ver README",
            metadata={"engine": "openhands", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify


# --------------------------------------------------------------------------- #
# Google ADK Adapter
# --------------------------------------------------------------------------- #

class GoogleADKAdapter(CapabilityImpl):
    name = "adk_agent"
    category = CapabilityCategory.INTERNAL
    description = "Google ADK — constrói agentes via Gemini"

    def __init__(self, engine_path: str = "engines/google-adk"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("google.adk", "GEMINI_API_KEY")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[adk] task={task!r}")
        try:
            from google.adk.agents import LlmAgent  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("Google ADK", self.engine_path,
                                          "export GEMINI_API_KEY=...") + f"Erro: {e}",
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="ADK Runner API varia por versão — ver engines/google-adk/README",
            metadata={"engine": "adk", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify


# --------------------------------------------------------------------------- #
# AutoGen Adapter
# --------------------------------------------------------------------------- #

class AutoGenAdapter(CapabilityImpl):
    name = "autogen_conversation"
    category = CapabilityCategory.INTERNAL
    description = "Microsoft AutoGen — multi-agent conversation"

    def __init__(self, engine_path: str = "engines/autogen"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("autogen")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[autogen] task={task!r}")
        try:
            import autogen  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("AutoGen", self.engine_path) + f"Erro: {e}",
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="AutoGen API varia por versão (0.2 vs 0.4) — ver engines/autogen/README",
            metadata={"engine": "autogen", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify


# --------------------------------------------------------------------------- #
# CrewAI Adapter
# --------------------------------------------------------------------------- #

class CrewAIAdapter(CapabilityImpl):
    name = "crewai_crew"
    category = CapabilityCategory.INTERNAL
    description = "CrewAI — role-based multi-agent crews"

    def __init__(self, engine_path: str = "engines/crewai"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("crewai")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[crewai] task={task!r}")
        try:
            from crewai import Agent, Task, Crew  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("CrewAI", self.engine_path) + f"Erro: {e}",
                finished_at=time.time(),
            )
        try:
            agents_config = inputs.get("agents", [
                {"role": "Researcher", "goal": "Find information",
                 "backstory": "Expert researcher"}
            ])
            agents = [
                Agent(role=a["role"], goal=a["goal"],
                      backstory=a.get("backstory", ""))
                for a in agents_config
            ]
            tasks = [Task(description=task, agent=agents[0],
                          expected_output="Detailed response")]
            crew = Crew(agents=agents, tasks=tasks,
                        process=inputs.get("process", "sequential"))
            result = crew.kickoff()
            return StepResult(
                success=True, output={"result": str(result), "raw": result},
                metadata={"engine": "crewai",
                          "duration_s": round(time.time() - started, 2)},
                finished_at=time.time(),
            )
        except Exception as e:
            return StepResult(success=False, error=f"{type(e).__name__}: {e}",
                              finished_at=time.time())

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        return VerificationResult(
            passed=True,
            checks=[{"name": "has_result", "passed": bool(result.output.get("result"))}],
        )


# --------------------------------------------------------------------------- #
# LangGraph Adapter
# --------------------------------------------------------------------------- #

class LangGraphAdapter(CapabilityImpl):
    name = "langgraph_workflow"
    category = CapabilityCategory.INTERNAL
    description = "LangGraph — stateful agent graphs"

    def __init__(self, engine_path: str = "engines/langgraph"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("langgraph")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[langgraph] task={task!r}")
        try:
            from langgraph.graph import StateGraph, END  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("LangGraph", self.engine_path) + f"Erro: {e}",
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="LangGraph requer definição de grafo — ver examples/",
            metadata={"engine": "langgraph", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify


# --------------------------------------------------------------------------- #
# Smolagents Adapter
# --------------------------------------------------------------------------- #

class SmolagentsAdapter(CapabilityImpl):
    name = "smolagents_code"
    category = CapabilityCategory.CODING
    description = "HuggingFace smolagents — code-based agents"

    def __init__(self, engine_path: str = "engines/smolagents"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("smolagents", "GEMINI_API_KEY")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[smolagents] task={task!r}")
        try:
            from smolagents import CodeAgent, LiteLLMModel  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("smolagents", self.engine_path,
                                          "export GEMINI_API_KEY=...") + f"Erro: {e}",
                finished_at=time.time(),
            )
        try:
            model = LiteLLMModel(
                model_id=f"gemini/{inputs.get('model', 'gemini-2.5-flash')}",
                api_key=os.environ.get("GEMINI_API_KEY", ""),
            )
            agent = CodeAgent(tools=[], model=model)
            result = agent.run(task)
            return StepResult(
                success=True, output={"answer": str(result), "raw": result},
                metadata={"engine": "smolagents",
                          "duration_s": round(time.time() - started, 2)},
                finished_at=time.time(),
            )
        except Exception as e:
            return StepResult(success=False, error=f"{type(e).__name__}: {e}",
                              finished_at=time.time())

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        return VerificationResult(
            passed=True,
            checks=[{"name": "has_answer", "passed": bool(result.output.get("answer"))}],
        )


# --------------------------------------------------------------------------- #
# Camel Adapter
# --------------------------------------------------------------------------- #

class CamelAdapter(CapabilityImpl):
    name = "camel_roleplay"
    category = CapabilityCategory.INTERNAL
    description = "Camel-AI — role-playing multi-agent"

    def __init__(self, engine_path: str = "engines/camel"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("camel")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[camel] task={task!r}")
        try:
            from camel.agents import ChatAgent  # type: ignore
        except ImportError as e:
            return StepResult(
                success=False,
                error=_not_installed_msg("Camel", self.engine_path) + f"Erro: {e}",
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="Camel API rich — ver engines/camel/examples/",
            metadata={"engine": "camel", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify


# --------------------------------------------------------------------------- #
# Anthropic Computer Use Adapter
# --------------------------------------------------------------------------- #

class AnthropicCUAAdapter(CapabilityImpl):
    name = "computer_cua_anthropic"
    category = CapabilityCategory.COMPUTER
    description = "Anthropic Computer Use — controla desktop via Claude"

    def __init__(self, engine_path: str = "engines/anthropic-quickstarts"):
        self.engine_path = engine_path

    def health(self) -> bool:
        return _health_check("anthropic", "ANTHROPIC_API_KEY")

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task = inputs.get("task")
        if not task:
            return StepResult(success=False, error="task é obrigatório")
        started = time.time()
        ctx.logger(f"[anthropic_cua] task={task!r}")
        try:
            import anthropic  # type: ignore
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY não definida")
        except (ImportError, RuntimeError) as e:
            return StepResult(
                success=False,
                error=(
                    f"Anthropic Computer Use não pronto. Para activar:\n"
                    f"  pip install anthropic\n"
                    f"  export ANTHROPIC_API_KEY=sk-ant-...\n"
                    f"  Ver {self.engine_path}/computer-use-demo/ para Docker setup\n"
                    f"Erro: {e}"
                ),
                finished_at=time.time(),
            )
        return StepResult(
            success=False,
            error="Computer Use requer Docker + VNC setup — ver engines/anthropic-quickstarts/computer-use-demo/",
            metadata={"engine": "anthropic_cua", "task": task,
                      "duration_s": round(time.time() - started, 2)},
            finished_at=time.time(),
        )

    verify = _default_verify
