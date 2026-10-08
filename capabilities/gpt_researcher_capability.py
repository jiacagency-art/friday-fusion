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
        # Path para config custom (usa Gemini via endpoint OpenAI-compatible)
        self._config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "gpt_researcher_config.json"
        )

    def _check_availability(self) -> tuple[bool, str]:
        if self._checked:
            return self._available, getattr(self, "_reason", "")
        self._checked = True
        try:
            from gpt_researcher import GPTResearcher  # type: ignore
            # GPT-Researcher precisa de OPENAI_API_KEY (não funciona bem com só Gemini)
            # Também precisa de TAVILY_API_KEY para retriever
            has_openai = bool(os.environ.get("OPENAI_API_KEY"))
            has_tavily = bool(os.environ.get("TAVILY_API_KEY"))
            if not has_openai:
                self._available = False
                self._reason = "GPT-Researcher requer OPENAI_API_KEY (Gemini não suportado directamente)"
            elif not has_tavily:
                self._available = False
                self._reason = "GPT-Researcher requer TAVILY_API_KEY para search"
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

            # Construir config com a API key do Gemini (do ambiente)
            config_path = self._build_runtime_config()

            researcher = GPTResearcher(
                query=query,
                report_type=report_type,
                config_path=config_path,
            )

            async def _run():
                # API correcta do GPT-Researcher: conduct_research() + write_report()
                await researcher.conduct_research()
                report = await researcher.write_report()
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

    def _build_runtime_config(self) -> Optional[str]:
        """
        Cria config file runtime com a API key do ambiente.
        GPT-Researcher precisa da key no JSON config.
        """
        import json
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        openai_key = os.environ.get("OPENAI_API_KEY", "")

        config = {
            "temperature": 0.2,
            "max_tokens": 4000,
        }

        if gemini_key:
            config["llm_provider"] = "generic"
            config["llm_model"] = "gemini-3.1-pro-preview"
            config["openai_api_key"] = gemini_key
            config["openai_base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai"
            # Embedding: Gemini não tem endpoint de embedding OpenAI-compatible
            # usar Fake embeddings como fallback
            config["embedding_provider"] = "ollama"
            config["embedding_model"] = "nomic-embed-text"
        elif openai_key:
            config["llm_provider"] = "openai"
            config["llm_model"] = "gpt-4o-mini"
            config["openai_api_key"] = openai_key
        else:
            return None

        # Escrever config file temporário
        import tempfile
        config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="gpt_researcher_"
        )
        json.dump(config, config_file, indent=2)
        config_file.close()
        return config_file.name
