"""
FRIDAY Engines — Ligação aos 5 engines reais
============================================
Este módulo liga o FRIDAY Core aos 5 engines reais:

1. OpenHands (openhands-ai) → executor principal
2. Hermes Agent → research engine (código lido, Python 3.14 necessário para runtime)
3. AutoGen (autogen_agentchat 0.7) → orquestrador de agentes
4. Browser Use → browser engine
5. Mem0 → memória semântica

Cada engine tem:
- health() — verifica se está disponível
- execute() — executa uma acção real
- fallback — se o engine falhar, há uma alternativa

As APIs usadas são as REAIS de cada pacote (ver engines/ para código fonte).
"""

from __future__ import annotations

import os
import time
import asyncio
import json
from typing import Any, Optional
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Engine Health Status
# --------------------------------------------------------------------------- #

@dataclass
class EngineStatus:
    name: str
    available: bool
    version: str = ""
    reason: str = ""
    last_check: float = 0.0


# --------------------------------------------------------------------------- #
# 1. OPENHANDS — Executor principal
# --------------------------------------------------------------------------- #

class OpenHandsEngine:
    """
    OpenHands runtime — executor principal do FRIDAY.

    API real (openhands-ai 1.11.0):
        from openhands.sdk import Agent, AgentBuilder

    Quando o FRIDAY recebe um objetivo de coding/execução,
    passa para o OpenHands executar.
    """

    def __init__(self):
        self._status: Optional[EngineStatus] = None

    def health(self) -> EngineStatus:
        if self._status and time.time() - self._status.last_check < 60:
            return self._status
        try:
            import openhands  # type: ignore
            version = getattr(openhands, "__version__", "?")
            # Verificar SDK disponível
            try:
                from openhands.sdk import Agent  # type: ignore
                self._status = EngineStatus(
                    name="openhands", available=True, version=version,
                    last_check=time.time(),
                )
            except ImportError:
                self._status = EngineStatus(
                    name="openhands", available=False, version=version,
                    reason="openhands instalado mas SDK não disponível (requer config Docker)",
                    last_check=time.time(),
                )
        except ImportError:
            self._status = EngineStatus(
                name="openhands", available=False,
                reason="pip install openhands-ai",
                last_check=time.time(),
            )
        return self._status

    def execute(self, task: str, working_dir: str = "/tmp/friday_openhands",
                **kwargs) -> dict[str, Any]:
        """
        Executa uma tarefa de coding/execução no OpenHands.

        Retorna dict com: success, output, error
        """
        status = self.health()
        if not status.available:
            return {"success": False, "error": f"OpenHands indisponível: {status.reason}",
                    "fallback": "manual"}

        try:
            # API real do OpenHands SDK
            from openhands.sdk import Agent, AgentBuilder  # type: ignore
            # Construir agente — requer LLM config
            llm_config = self._build_llm_config()
            if not llm_config:
                return {"success": False,
                        "error": "Sem LLM configurado para OpenHands (OPENAI_API_KEY ou GEMINI_API_KEY)"}

            # OpenHands Agent API (varia por versão — esta é a 1.11.0)
            # Em produção: agent = Agent(llm=llm_config, workdir=working_dir)
            #              result = agent.run(task)
            # Como o SDK requer config completa, retornamos info útil
            return {
                "success": False,
                "error": "OpenHands SDK requer config Docker + LLM completa — ver engines/OpenHands/",
                "task": task,
                "engine": "openhands",
                "version": status.version,
                "fallback_suggestion": "Para coding simples, usar smolagents ou hermes",
            }
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def _build_llm_config(self):
        """Constrói config LLM para OpenHands."""
        # OpenHands usa litellm por baixo
        if os.environ.get("OPENAI_API_KEY"):
            return {"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}
        if os.environ.get("GEMINI_API_KEY"):
            return {"model": "gemini/gemini-2.5-flash",
                    "api_key": os.environ["GEMINI_API_KEY"]}
        return None


# --------------------------------------------------------------------------- #
# 2. HERMES AGENT — Research engine
# --------------------------------------------------------------------------- #

class HermesEngine:
    """
    Hermes Agent (NousResearch) — research engine self-improving.

    API real (ver engines/hermes-agent/):
        from hermes import HermesAgent
        agent = HermesAgent(model="...")
        result = agent.run("research task")

    Nota: hermes-agent requer Python 3.14 (não disponível neste env).
    O código está em engines/hermes-agent/ para referência.
    Em produção com Python 3.14+, este engine activa-se.
    """

    def __init__(self, engine_path: str = "engines/hermes-agent"):
        self.engine_path = engine_path
        self._status: Optional[EngineStatus] = None

    def health(self) -> EngineStatus:
        if self._status and time.time() - self._status.last_check < 60:
            return self._status
        try:
            import sys
            sys.path.insert(0, self.engine_path)
            import hermes  # type: ignore
            version = getattr(hermes, "__version__", "?")
            self._status = EngineStatus(
                name="hermes", available=True, version=version,
                last_check=time.time(),
            )
        except ImportError as e:
            self._status = EngineStatus(
                name="hermes", available=False,
                reason=f"hermes-agent requer Python 3.14 (env tem 3.12). Código em {self.engine_path}/",
                last_check=time.time(),
            )
        return self._status

    def execute(self, task: str, **kwargs) -> dict[str, Any]:
        """Executa research via Hermes."""
        status = self.health()
        if not status.available:
            return {"success": False, "error": f"Hermes indisponível: {status.reason}",
                    "fallback": "web_search"}

        try:
            # API real do Hermes (quando Python 3.14 disponível)
            from hermes import HermesAgent  # type: ignore
            agent = HermesAgent(
                model=kwargs.get("model", "gpt-4o"),
                api_key=os.environ.get("OPENAI_API_KEY", ""),
            )
            result = agent.run(task)
            return {"success": True, "output": result, "engine": "hermes"}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# 3. AUTOGEN — Orquestrador de agentes
# --------------------------------------------------------------------------- #

class AutoGenEngine:
    """
    AutoGen 0.7 — orquestrador de agentes multi-conversa.

    API real (autogen-agentchat 0.7.5):
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.teams import RoundRobinGroupChat
        from autogen_agentchat.conditions import TextMentionTermination

    Quando o FRIDAY precisa de dividir trabalho entre múltiplos agentes.
    """

    def __init__(self):
        self._status: Optional[EngineStatus] = None

    def health(self) -> EngineStatus:
        if self._status and time.time() - self._status.last_check < 60:
            return self._status
        try:
            from autogen_agentchat.agents import AssistantAgent  # type: ignore
            from autogen_agentchat.teams import RoundRobinGroupChat  # type: ignore
            import autogen_agentchat
            version = getattr(autogen_agentchat, "__version__", "?")
            self._status = EngineStatus(
                name="autogen", available=True, version=version,
                last_check=time.time(),
            )
        except ImportError as e:
            self._status = EngineStatus(
                name="autogen", available=False,
                reason=f"pip install autogen-agentchat: {e}",
                last_check=time.time(),
            )
        return self._status

    def execute(self, task: str, agents_config: Optional[list[dict]] = None,
                **kwargs) -> dict[str, Any]:
        """
        Cria uma equipa de agentes e executa a tarefa.

        Args:
            task: descrição da tarefa
            agents_config: lista de configs de agentes
                          [{"name": "researcher", "system_message": "..."}]

        Returns:
            dict com success, output, agents_used
        """
        status = self.health()
        if not status.available:
            return {"success": False, "error": f"AutoGen indisponível: {status.reason}"}

        try:
            from autogen_agentchat.agents import AssistantAgent  # type: ignore
            from autogen_agentchat.teams import RoundRobinGroupChat  # type: ignore
            from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination  # type: ignore

            # Config default: 2 agentes (researcher + writer)
            if agents_config is None:
                agents_config = [
                    {"name": "Researcher",
                     "system_message": "You are a researcher. Find information and pass it to the Writer. Reply TERMINATE when done."},
                    {"name": "Writer",
                     "system_message": "You are a writer. Take research from Researcher and write a final report. Reply TERMINATE when done."},
                ]

            # LLM config
            llm_config = self._build_llm_config()
            if not llm_config:
                return {"success": False,
                        "error": "Sem LLM configurado para AutoGen (OPENAI_API_KEY)"}

            # Construir agentes
            agents = []
            for ac in agents_config:
                agent = AssistantAgent(
                    name=ac["name"],
                    model=llm_config,
                    system_message=ac["system_message"],
                )
                agents.append(agent)

            # Criar team
            termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)
            team = RoundRobinGroupChat(agents, termination_condition=termination)

            # Executar (async)
            async def _run():
                result = await team.run(task=task)
                return result

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(asyncio.run, _run).result(timeout=300)
                else:
                    result = loop.run_until_complete(_run())
            except RuntimeError:
                result = asyncio.run(_run())

            return {
                "success": True,
                "output": str(result),
                "agents_used": [ac["name"] for ac in agents_config],
                "engine": "autogen",
                "version": status.version,
            }
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def _build_llm_config(self):
        """Config LLM para AutoGen (usa OpenAI client format)."""
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        return {"model": "gpt-4o-mini", "api_key": os.environ["OPENAI_API_KEY"]}


# --------------------------------------------------------------------------- #
# 4. BROWSER USE — Browser engine
# --------------------------------------------------------------------------- #

class BrowserUseEngine:
    """
    Browser Use — browser engine LLM-driven.

    API real (browser-use latest):
        from browser_use import Agent
        agent = Agent(task="...", llm=ChatOpenAI(...))
        result = await agent.run()

    Quando o FRIDAY precisa de navegar na web.
    """

    def __init__(self):
        self._status: Optional[EngineStatus] = None

    def health(self) -> EngineStatus:
        if self._status and time.time() - self._status.last_check < 60:
            return self._status
        try:
            from browser_use import Agent  # type: ignore
            version = "latest"
            self._status = EngineStatus(
                name="browser_use", available=True, version=version,
                last_check=time.time(),
            )
        except ImportError as e:
            self._status = EngineStatus(
                name="browser_use", available=False,
                reason=f"pip install browser-use: {e}",
                last_check=time.time(),
            )
        return self._status

    def execute(self, task: str, url: Optional[str] = None,
                max_steps: int = 50, **kwargs) -> dict[str, Any]:
        """
        Executa uma tarefa no browser.

        Args:
            task: descrição em linguagem natural
            url: URL inicial opcional
            max_steps: limite de passos
        """
        status = self.health()
        if not status.available:
            return {"success": False, "error": f"Browser Use indisponível: {status.reason}"}

        try:
            from browser_use import Agent  # type: ignore
            from langchain_openai import ChatOpenAI  # type: ignore

            llm = self._build_llm()
            if llm is None:
                return {"success": False,
                        "error": "Sem LLM para Browser Use (GEMINI_API_KEY ou OPENAI_API_KEY)"}

            agent_kwargs: dict[str, Any] = {
                "task": task,
                "llm": llm,
                "max_steps": max_steps,
            }
            if url:
                agent_kwargs["start_url"] = url

            agent = Agent(**agent_kwargs)

            async def _run():
                return await agent.run()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        history = pool.submit(asyncio.run, _run).result(timeout=300)
                else:
                    history = loop.run_until_complete(_run())
            except RuntimeError:
                history = asyncio.run(_run())

            return {
                "success": True,
                "output": {
                    "final_url": getattr(history, "final_url", None),
                    "extracted": getattr(history, "extracted_content", None),
                    "steps_taken": len(getattr(history, "steps", []) or []),
                },
                "engine": "browser_use",
            }
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def _build_llm(self):
        """Constrói LLM para Browser Use (langchain_openai)."""
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except ImportError:
            return None

        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if gemini_key:
            return ChatOpenAI(
                model="gemini-3.1-pro-preview",
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                temperature=0.2,
            )
        elif openai_key:
            return ChatOpenAI(model="gpt-4o", api_key=openai_key, temperature=0.2)
        return None


# --------------------------------------------------------------------------- #
# 5. MEM0 — Memória semântica
# --------------------------------------------------------------------------- #

class Mem0Engine:
    """
    Mem0 — memória semântica para AI agents.

    API real (mem0ai 2.2.1):
        from mem0 import Memory
        m = Memory()
        m.add("content", user_id="user1")
        results = m.search("query", user_id="user1")

    Tudo o que o FRIDAY faz é guardado no Mem0.
    No início de cada tarefa, consulta o Mem0.
    """

    def __init__(self):
        self._memory = None
        self._status: Optional[EngineStatus] = None

    def health(self) -> EngineStatus:
        if self._status and time.time() - self._status.last_check < 60:
            return self._status
        try:
            from mem0 import Memory  # type: ignore
            # Tentar inicializar
            self._memory = Memory()
            self._status = EngineStatus(
                name="mem0", available=True, version="2.2.1",
                last_check=time.time(),
            )
        except ImportError as e:
            self._status = EngineStatus(
                name="mem0", available=False,
                reason=f"pip install mem0ai: {e}",
                last_check=time.time(),
            )
        except Exception as e:
            # Mem0 pode falhar se não tiver OpenAI key
            self._status = EngineStatus(
                name="mem0", available=False,
                reason=f"Mem0 inicializa mas precisa OPENAI_API_KEY: {e}",
                last_check=time.time(),
            )
        return self._status

    def add(self, content: str, user_id: str = "friday",
            metadata: Optional[dict] = None) -> dict[str, Any]:
        """Adiciona uma memória."""
        status = self.health()
        if not status.available or self._memory is None:
            return {"success": False, "error": status.reason}

        try:
            result = self._memory.add(content, user_id=user_id, metadata=metadata or {})
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search(self, query: str, user_id: str = "friday",
               top_k: int = 5) -> dict[str, Any]:
        """Pesquisa memórias relevantes."""
        status = self.health()
        if not status.available or self._memory is None:
            return {"success": False, "error": status.reason, "results": []}

        try:
            results = self._memory.search(query, user_id=user_id, top_k=top_k)
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e), "results": []}

    def get_all(self, user_id: str = "friday") -> dict[str, Any]:
        """Lista todas as memórias."""
        status = self.health()
        if not status.available or self._memory is None:
            return {"success": False, "error": status.reason, "results": []}
        try:
            results = self._memory.get_all(user_id=user_id)
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e), "results": []}


# --------------------------------------------------------------------------- #
# FRIDAY ENGINES — agregador
# --------------------------------------------------------------------------- #

class FridayEngines:
    """
    Aggregador dos 5 engines do FRIDAY.

    Uso:
        engines = FridayEngines()
        engines.health_check()  # verifica todos
        engines.mem0.add("...")
        engines.browser.execute(task="...")
    """

    def __init__(self):
        self.openhands = OpenHandsEngine()
        self.hermes = HermesEngine()
        self.autogen = AutoGenEngine()
        self.browser = BrowserUseEngine()
        self.mem0 = Mem0Engine()

    def health_check(self) -> dict[str, EngineStatus]:
        """Verifica saúde de todos os engines."""
        return {
            "openhands": self.openhands.health(),
            "hermes": self.hermes.health(),
            "autogen": self.autogen.health(),
            "browser_use": self.browser.health(),
            "mem0": self.mem0.health(),
        }

    def summary(self) -> dict[str, Any]:
        """Resumo para logging."""
        health = self.health_check()
        return {
            "engines": {
                name: {"available": s.available, "version": s.version,
                       "reason": s.reason if not s.available else ""}
                for name, s in health.items()
            },
            "available_count": sum(1 for s in health.values() if s.available),
            "total": len(health),
        }


# --------------------------------------------------------------------------- #
# Singleton
# --------------------------------------------------------------------------- #

_engines: Optional[FridayEngines] = None


def get_engines() -> FridayEngines:
    global _engines
    if _engines is None:
        _engines = FridayEngines()
    return _engines
