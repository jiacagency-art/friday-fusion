"""
CrewAI Multi-Agent Capability — REAL
====================================
Crew com 3 agentes especializados:
- Research Agent (usa GPT-Researcher / web_search)
- Browser Agent (usa Browser Use)
- Report Agent (compila resultados)

O Orchestrator do FRIDAY activa esta crew quando o objective é complexo
e requer múltiplas capacidades.
"""

from __future__ import annotations

import os
import time
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


class CrewAICapability(CapabilityImpl):
    """
    Crew AI com 3 agentes especializados.

    Inputs:
        task: str              — objective complexo
        agents: list[str]      — quais agentes activar (default: todos)
        verbose: bool          — log detalhado

    Output:
        dict com: final_result, agent_outputs
    """

    name = "crewai_crew"
    category = CapabilityCategory.INTERNAL
    description = "CrewAI — crew de 3 agentes (Research + Browser + Report) REAL"

    def __init__(self):
        self._checked = False
        self._available = False

    def _check_availability(self) -> tuple[bool, str]:
        if self._checked:
            return self._available, getattr(self, "_reason", "")
        self._checked = True
        try:
            from crewai import Agent, Task, Crew  # type: ignore
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
                self._available = False
                self._reason = "Sem LLM API key"
            else:
                self._available = True
                self._reason = ""
        except ImportError as e:
            self._available = False
            self._reason = f"crewai não instalado: {e}"
        return self._available, self._reason

    def health(self) -> bool:
        ok, _ = self._check_availability()
        return ok

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task_desc = inputs.get("task") or inputs.get("description")
        if not task_desc:
            return StepResult(success=False, error="task é obrigatório")

        ok, reason = self._check_availability()
        if not ok:
            return StepResult(
                success=False,
                error=f"CrewAI não disponível: {reason}",
                finished_at=time.time(),
            )

        started = time.time()
        agents_to_use = inputs.get("agents", ["researcher", "browser", "reporter"])
        verbose = inputs.get("verbose", False)
        ctx.logger(f"[crewai] task={task_desc!r} agents={agents_to_use}")

        try:
            from crewai import Agent, Task, Crew, Process  # type: ignore
            from crewai.llm import LLM  # type: ignore

            # Construir LLM
            llm = self._build_llm()
            if llm is None:
                return StepResult(
                    success=False,
                    error="Não foi possível construir LLM para CrewAI",
                    finished_at=time.time(),
                )

            # Construir agentes
            agents = []
            tasks = []

            if "researcher" in agents_to_use:
                researcher = Agent(
                    role="Research Specialist",
                    goal="Find comprehensive information about the topic using web research",
                    backstory="""You are an expert researcher specialized in emerging markets,
                    particularly Angola. You find relevant companies, people, and opportunities
                    by analyzing multiple sources.""",
                    llm=llm,
                    verbose=verbose,
                    allow_delegation=False,
                )
                agents.append(researcher)
                tasks.append(Task(
                    description=f"Research the following topic thoroughly: {task_desc}. "
                                f"Identify key players, opportunities, and relevant data points.",
                    expected_output="A detailed research summary with key findings, "
                                   "company names, and contact information where available.",
                    agent=researcher,
                ))

            if "browser" in agents_to_use:
                browser_agent = Agent(
                    role="Browser Automation Specialist",
                    goal="Navigate websites and extract specific information",
                    backstory="""You are an expert at navigating websites, finding specific
                    pages, and extracting structured information like contact details,
                    company info, and decision-maker names.""",
                    llm=llm,
                    verbose=verbose,
                    allow_delegation=False,
                )
                agents.append(browser_agent)
                tasks.append(Task(
                    description="Based on the research, navigate to the most relevant websites "
                               "and extract contact information, decision-maker names, and "
                               "company details.",
                    expected_output="A structured list of contacts and company information "
                                   "extracted from websites.",
                    agent=browser_agent,
                    context=[tasks[-1]] if tasks else [],
                ))

            if "reporter" in agents_to_use:
                reporter = Agent(
                    role="Commercial Report Writer",
                    goal="Compile findings into a professional commercial proposal",
                    backstory="""You are a senior business analyst who transforms raw research
                    data into actionable commercial proposals and reports. You write in
                    Portuguese (Angola) when appropriate.""",
                    llm=llm,
                    verbose=verbose,
                    allow_delegation=False,
                )
                agents.append(reporter)
                tasks.append(Task(
                    description="Compile all research and extracted data into a comprehensive "
                               "commercial report. Include: executive summary, market analysis, "
                               "company profiles, opportunities, and recommended next steps.",
                    expected_output="A complete commercial report in Markdown format with "
                                   "sections: Resumo Executivo, Análise de Mercado, "
                                   "Perfil das Empresas, Oportunidades, Próximos Passos.",
                    agent=reporter,
                    context=tasks[:],
                ))

            if not agents:
                return StepResult(
                    success=False,
                    error="Nenhum agente especificado",
                    finished_at=time.time(),
                )

            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=verbose,
            )

            result = crew.kickoff()

            return StepResult(
                success=True,
                output={
                    "result": str(result),
                    "raw_result": result,
                    "agents_used": [a.role for a in agents],
                    "tasks_completed": len(tasks),
                },
                artifacts=[
                    {"type": "report", "format": "markdown",
                     "content": str(result), "task": task_desc},
                ],
                metadata={
                    "engine": "crewai",
                    "duration_s": round(time.time() - started, 2),
                    "agents": [a.role for a in agents],
                },
                finished_at=time.time(),
            )

        except Exception as e:
            ctx.logger(f"[crewai] erro: {type(e).__name__}: {e}", level="error")
            return StepResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                metadata={"engine": "crewai", "task": task_desc},
                finished_at=time.time(),
            )

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        output = result.output or {}
        checks = [
            {"name": "has_result", "passed": bool(output.get("result"))},
            {"name": "has_agents", "passed": len(output.get("agents_used", [])) > 0},
            {"name": "result_substantial", "passed": len(output.get("result", "")) > 200},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks), checks=checks)

    def _build_llm(self):
        """Constrói LLM para CrewAI."""
        try:
            from crewai.llm import LLM  # type: ignore
        except ImportError:
            return None

        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if gemini_key:
            return LLM(
                model="gemini/gemini-2.5-flash",
                api_key=gemini_key,
            )
        elif openai_key:
            return LLM(model="gpt-4o", api_key=openai_key)
        return None
