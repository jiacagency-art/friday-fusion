"""
GPT-Researcher Capability — REAL deep research
==============================================
Substitui o web_search simples pelo GPT-Researcher quando disponível.

GPT-Researcher faz research multi-step:
1. Gera sub-queries a partir da pergunta
2. Pesquisa cada uma (DuckDuckGo + scraping)
3. Avalia relevância de cada fonte
4. Compila relatório estruturado

Requer LLM API key. Sem LLM, faz fallback para WebSearchCapability (DuckDuckGo simples).
"""

from __future__ import annotations

import os
import time
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)
from capabilities.web_search import WebSearchCapability


class GPTResearcherCapability(CapabilityImpl):
    """
    Research profundo via GPT-Researcher.

    Inputs:
        query: str           — pergunta de research
        max_results: int     — limite de fontes (default 10)
        report_type: str     — "research_report" | "summary_report" | "detailed_report"

    Output:
        dict com: report (markdown), sources, questions, cost
    """

    name = "web_search"  # mesmo nome — substitui o WebSearchCapability no registry
    category = CapabilityCategory.RESEARCH
    description = "GPT-Researcher — research profundo multi-step (REAL)"

    def __init__(self):
        self._fallback = WebSearchCapability()
        self._checked = False
        self._available = False

    def _check_availability(self) -> tuple[bool, str]:
        if self._checked:
            return self._available, getattr(self, "_reason", "")
        self._checked = True
        try:
            from gpt_researcher import GPTResearcher  # type: ignore
            # Verificar LLM
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
                self._available = False
                self._reason = "Sem LLM API key"
            else:
                self._available = True
                self._reason = ""
        except ImportError as e:
            self._available = False
            self._reason = f"gpt-researcher não instalado: {e}"
        return self._available, self._reason

    def health(self) -> bool:
        ok, _ = self._check_availability()
        return ok

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        query = inputs.get("query") or inputs.get("q")
        if not query:
            return StepResult(success=False, error="query é obrigatório")

        ok, reason = self._check_availability()
        if not ok:
            ctx.logger(f"[gpt_researcher] indisponível ({reason}) — fallback para DuckDuckGo", level="warn")
            return self._fallback.execute(inputs, ctx)

        started = time.time()
        report_type = inputs.get("report_type", "research_report")
        ctx.logger(f"[gpt_researcher] query={query!r} type={report_type}")

        try:
            from gpt_researcher import GPTResearcher  # type: ignore
            import asyncio

            researcher = GPTResearcher(
                query=query,
                report_type=report_type,
                max_sections=int(inputs.get("max_results", 3)),
            )

            async def _run():
                report = await researcher.research()
                return report

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        report = pool.submit(asyncio.run, _run).result(timeout=600)
                else:
                    report = loop.run_until_complete(_run())
            except RuntimeError:
                report = asyncio.run(_run())

            # Extrair fontes
            sources = []
            try:
                source_objs = researcher.get_source_urls()
                sources = [{"url": u} for u in source_objs] if source_objs else []
            except Exception:
                pass

            return StepResult(
                success=True,
                output={
                    "report": report,
                    "sources": sources,
                    "query": query,
                },
                artifacts=[
                    {"type": "report", "format": "markdown", "content": report, "query": query},
                ],
                metadata={
                    "engine": "gpt_researcher",
                    "report_type": report_type,
                    "duration_s": round(time.time() - started, 2),
                    "sources_count": len(sources),
                },
                finished_at=time.time(),
            )

        except Exception as e:
            ctx.logger(f"[gpt_researcher] erro: {type(e).__name__}: {e}", level="error")
            ctx.logger("[gpt_researcher] fallback para DuckDuckGo", level="warn")
            return self._fallback.execute(inputs, ctx)

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        # Se veio do GPT-Researcher, verificar report
        if result.metadata.get("engine") == "gpt_researcher":
            report = result.output.get("report", "")
            checks = [
                {"name": "has_report", "passed": bool(report)},
                {"name": "report_substantial", "passed": len(report) > 500,
                 "actual_len": len(report)},
                {"name": "has_sources", "passed": len(result.output.get("sources", [])) > 0},
            ]
        else:
            # Fallback DuckDuckGo — usar verificação do fallback
            return self._fallback.verify(result, inputs)
        return VerificationResult(passed=all(c["passed"] for c in checks), checks=checks)
