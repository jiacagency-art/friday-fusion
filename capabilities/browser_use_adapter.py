"""
Browser Use Adapter — REAL implementation
=========================================
Wrapper real para o engine Browser Use (pip install browser-use).

Requer:
- browser-use instalado
- playwright + chromium instalados
- LLM API key (GEMINI_API_KEY ou OPENAI_API_KEY)

O Browser Use é LLM-driven: cada acção no browser é decidida pelo LLM.
Por isso, sem LLM disponível, health()=False.
"""

from __future__ import annotations

import os
import time
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


class BrowserUseAdapter(CapabilityImpl):
    """
    Adapter REAL para Browser Use — agente autónomo de navegador.

    Inputs:
        task: str        — descrição da tarefa em linguagem natural
        url: str|None    — URL inicial opcional
        max_steps: int   — limite de passos (default 50)

    Output:
        dict com: final_url, history, extracted_content, steps_taken
    """

    name = "browser_use"
    category = CapabilityCategory.BROWSER
    description = "Browser Use — agente autónomo de navegador (REAL)"

    def __init__(self):
        self._checked = False
        self._available = False

    def _check_availability(self) -> tuple[bool, str]:
        """Verifica se tudo está pronto. Retorna (ok, reason)."""
        if self._checked:
            return self._available, self._reason if hasattr(self, '_reason') else ""
        self._checked = True
        try:
            from browser_use import Agent  # type: ignore
            self._available = True
            # Verificar LLM
            has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
            has_openai = bool(os.environ.get("OPENAI_API_KEY"))
            if not (has_gemini or has_openai):
                self._available = False
                self._reason = "Sem LLM API key (GEMINI_API_KEY ou OPENAI_API_KEY)"
            else:
                self._reason = ""
        except ImportError as e:
            self._available = False
            self._reason = f"browser-use não instalado: {e}"
        return self._available, self._reason

    def health(self) -> bool:
        ok, _ = self._check_availability()
        return ok

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task_desc = inputs.get("task") or inputs.get("description")
        if not task_desc:
            return StepResult(success=False, error="task (descrição) é obrigatório")

        ok, reason = self._check_availability()
        if not ok:
            return StepResult(
                success=False,
                error=f"Browser Use não disponível: {reason}",
                finished_at=time.time(),
            )

        started = time.time()
        ctx.logger(f"[browser_use] task={task_desc!r}")

        try:
            # Import dinâmico para evitar carregar pesado no startup
            from browser_use import Agent  # type: ignore
            import asyncio

            # Configurar LLM — tentar Gemini primeiro (via LiteLLM), depois OpenAI
            llm = self._build_llm()
            if llm is None:
                return StepResult(
                    success=False,
                    error="Não foi possível construir LLM para Browser Use",
                    finished_at=time.time(),
                )

            # Construir agente
            agent_kwargs: dict[str, Any] = {
                "task": task_desc,
                "llm": llm,
                "max_steps": int(inputs.get("max_steps", 50)),
            }
            if inputs.get("url"):
                agent_kwargs["start_url"] = inputs["url"]

            agent = Agent(**agent_kwargs)

            # Browser Use é async — correr num event loop
            async def _run():
                return await agent.run()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Já estamos num loop — criar nova thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        history = pool.submit(asyncio.run, _run).result(timeout=300)
                else:
                    history = loop.run_until_complete(_run())
            except RuntimeError:
                history = asyncio.run(_run())

            # Extrair resultados
            final_url = getattr(history, "final_url", None) or getattr(history, "url", None)
            extracted = getattr(history, "extracted_content", None)
            steps = getattr(history, "steps", [])

            return StepResult(
                success=True,
                output={
                    "final_url": str(final_url) if final_url else None,
                    "history": str(history)[:5000],  # truncar para não estoirar memória
                    "extracted": extracted if extracted else None,
                    "steps_taken": len(steps) if steps else 0,
                },
                metadata={
                    "engine": "browser_use",
                    "duration_s": round(time.time() - started, 2),
                    "task": task_desc,
                },
                finished_at=time.time(),
            )

        except Exception as e:
            ctx.logger(f"[browser_use] erro: {type(e).__name__}: {e}", level="error")
            return StepResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                metadata={"engine": "browser_use", "task": task_desc},
                finished_at=time.time(),
            )

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        checks = [
            {"name": "has_output", "passed": bool(result.output)},
            {"name": "has_history", "passed": bool(result.output.get("history"))},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks), checks=checks)

    def _build_llm(self):
        """Constrói o LLM para o Browser Use. Tenta Gemini (via ChatOpenAI compat), depois OpenAI."""
        # Browser Use usa langchain ChatOpenAI por defeito
        # Gemini funciona via endpoint OpenAI-compatible
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except ImportError:
            try:
                from langchain.chat_models import ChatOpenAI  # type: ignore
            except ImportError:
                return None

        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if gemini_key:
            # Gemini via endpoint OpenAI-compatible
            return ChatOpenAI(
                model="gemini-3.1-pro-preview",
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                temperature=0.2,
            )
        elif openai_key:
            return ChatOpenAI(model="gpt-4o", api_key=openai_key, temperature=0.2)
        return None
