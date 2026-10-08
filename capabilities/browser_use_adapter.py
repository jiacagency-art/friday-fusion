"""Browser Use Adapter — wrapper para o engine Browser Use."""

from __future__ import annotations
import time
from typing import Any
from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


class BrowserUseAdapter(CapabilityImpl):
    name = "browser_use"
    category = CapabilityCategory.BROWSER
    description = "Browser Use — agente autónomo de navegador"

    def __init__(self, engine_path: str = "engines/browser-use"):
        self.engine_path = engine_path
        self._agent_cls = None
        self._checked = False

    def _lazy_load(self):
        if self._agent_cls is not None:
            return self._agent_cls
        try:
            from browser_use import Agent  # type: ignore
            from browser_use.llm import ChatOpenAI  # type: ignore
            self._agent_cls = (Agent, ChatOpenAI)
            return self._agent_cls
        except ImportError as e:
            raise RuntimeError(
                f"Browser Use não instalado. Para activar:\n"
                f"  pip install -e {self.engine_path}\n"
                f"  playwright install chromium\n"
                f"  export OPENAI_API_KEY=...\n"
                f"Erro original: {e}"
            ) from e

    def health(self) -> bool:
        if self._checked:
            return self._agent_cls is not None
        self._checked = True
        try:
            import importlib
            importlib.import_module("browser_use")
            return True
        except ImportError:
            return False

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        task_desc = inputs.get("task") or inputs.get("description")
        if not task_desc:
            return StepResult(success=False, error="task (descrição) é obrigatório")
        started = time.time()
        ctx.logger(f"[browser_use] task={task_desc!r}")
        try:
            Agent, ChatOpenAI = self._lazy_load()
        except RuntimeError as e:
            return StepResult(success=False, error=str(e), finished_at=time.time())
        try:
            llm = ChatOpenAI(model="gpt-4o")
            agent = Agent(
                task=task_desc, llm=llm,
                **({"start_url": inputs["url"]} if inputs.get("url") else {}),
                max_steps=int(inputs.get("max_steps", 50)),
            )
            history = agent.run()
            return StepResult(
                success=True,
                output={
                    "final_url": getattr(history, "final_url", None),
                    "history": str(history),
                    "extracted": getattr(history, "extracted_content", None),
                },
                metadata={"engine": "browser_use",
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
        checks = [
            {"name": "has_output", "passed": bool(result.output)},
            {"name": "has_history", "passed": bool(result.output.get("history"))},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks), checks=checks)
