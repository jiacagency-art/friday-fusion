"""
FRIDAY Agent Factory
====================
"Criar agentes especializados quando necessário" (visão — autoexpansão).

O FRIDAY não é uma colecção descontrolada de agentes — é um núcleo com
especialistas registados on-demand. O Agent Factory:

1. Define papéis especializados (researcher, prospector, writer, analyst,
   engineer, designer, translator, social_media, accountant...).
2. Cria uma CapabilityImpl por papel, com prompt de sistema focado.
3. Regista no CapabilityRegistry como `agent_<role>`.
4. Se LLM (Gemini) configurado → raciocínio real; senão → modo regras
   (estrutura o trabalho com as capabilities existentes, sem fingir).

Uso:
    factory = AgentFactory(registry, llm_client)
    factory.create("researcher")          # cria + regista
    factory.create_all_defaults()         # cria os papéis essenciais
"""

from __future__ import annotations

import time
from typing import Any

from .types import Capability, CapabilityCategory, CapabilityImpl, StepResult, VerificationResult

ROLE_SPECS: dict[str, dict[str, Any]] = {
    "researcher": {
        "title": "Investigador",
        "goal": "Pesquisar a fundo e devolver factos com fontes",
        "tools": ["web_search", "research_owl", "briefing"],
        "system": "És o Investigador do FRIDAY. Pesquisas a fundo, citas fontes, nunca inventas factos.",
    },
    "prospector": {
        "title": "Prospetor Comercial",
        "goal": "Encontrar leads e oportunidades para a JIAC AGENCY",
        "tools": ["business_prospect", "web_search"],
        "system": "És o Prospetor do FRIDAY. Encontras empresas com necessidade real dos serviços JIAC (automação, IA, websites, software).",
    },
    "writer": {
        "title": "Redactor",
        "goal": "Transformar pesquisa em relatórios e documentos claros",
        "tools": ["documents_create", "briefing"],
        "system": "És o Redactor do FRIDAY. Escreves relatórios claros e profissionais em português.",
    },
    "analyst": {
        "title": "Analista de Dados",
        "goal": "Analisar dados e produzir estatísticas e conclusões",
        "tools": ["data_analyze"],
        "system": "És o Analista do FRIDAY. Analisas dados, detectas padrões e explicas implicações de negócio.",
    },
    "engineer": {
        "title": "Engenheiro de Software",
        "goal": "Escrever e rever código, construir apps",
        "tools": ["coding_openhands", "smolagents_code"],
        "system": "És o Engenheiro do FRIDAY. Escreves código de qualidade, testas e documentas.",
    },
    "video_editor": {
        "title": "Editor de Vídeo",
        "goal": "Editar vídeos por instruções (cortes, legendas, formatos)",
        "tools": ["video_editor"],
        "system": "És o Editor de Vídeo do FRIDAY. Cortas, legendas, destacas e preparas versões por canal.",
    },
    "marketer": {
        "title": "Especialista em Marketing",
        "goal": "Campanhas, social media e comunicação JIAC",
        "tools": ["documents_create", "briefing", "email_send"],
        "system": "És o Marketer do FRIDAY. Crias mensagens que vendem sem exagerar.",
    },
}


class _SpecialistAgent(CapabilityImpl):
    """Um agente especializado do FRIDAY (categoria AGENT)."""

    def __init__(self, role: str, spec: dict[str, Any],
                 registry=None, llm_client=None, logger=None):
        self.role = role
        self.spec = spec
        self.name = f"agent_{role}"
        self.category = CapabilityCategory.AGENT
        self.description = f"{spec['title']} — {spec['goal']}"
        self.registry = registry
        self.llm_client = llm_client
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))
        self.created_at = time.time()

    def health(self) -> bool:
        return True

    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        instruction = str(inputs.get("instruction") or inputs.get("task")
                          or inputs.get("query") or "").strip()
        if not instruction:
            return StepResult(success=False,
                              error="instrução obrigatória p/ agente especializado",
                              finished_at=time.time())

        work: dict[str, Any] = {"role": self.role, "instruction": instruction}
        results_by_tool: dict[str, Any] = {}

        # 1. Executa as tools do papel (se registry disponível)
        if self.registry is not None:
            for tool_name in self.spec.get("tools", []):
                cap = self.registry.get(tool_name)
                if cap is None or not cap.impl.health():
                    results_by_tool[tool_name] = {"skipped": "indisponível"}
                    continue
                try:
                    tool_inputs = dict(inputs)
                    tool_inputs.setdefault("query", instruction)
                    tool_inputs.setdefault("task", instruction)
                    res = cap.impl.execute(tool_inputs, ctx)
                    results_by_tool[tool_name] = (
                        {"success": res.success, "output": res.output}
                        if res.success else {"success": False, "error": res.error})
                except Exception as e:
                    results_by_tool[tool_name] = {"success": False,
                                                  "error": str(e)[:200]}

        work["tool_results"] = results_by_tool

        # 2. Síntese: LLM se configurado, senão regras
        synthesis = self._synthesize(instruction, results_by_tool)
        work["synthesis"] = synthesis

        work["duration_s"] = round(time.time() - started, 2)
        return StepResult(success=True, output=work,
                          metadata={"agent": self.name, "tools_used":
                                    [t for t, r in results_by_tool.items()
                                     if isinstance(r, dict) and r.get("success")]},
                          finished_at=time.time())

    def _synthesize(self, instruction: str, tool_results: dict[str, Any]) -> str:
        ok_results = {t: r for t, r in tool_results.items()
                      if isinstance(r, dict) and r.get("success")}
        if self.llm_client is not None and getattr(self.llm_client, "is_configured", lambda: False)():
            try:
                context = "\n".join(f"- {t}: {str(r.get('output'))[:600]}"
                                    for t, r in ok_results.items())
                prompt = (f"{self.spec['system']}\n\nInstrução: {instruction}\n\n"
                          f"Resultados das ferramentas:\n{context}\n\n"
                          f"Dá a tua resposta especializada:")
                return self.llm_client.chat(prompt)
            except Exception as e:
                self.logger(f"[agent_{self.role}] LLM falhou: {e}", level="warn")

        # modo regras — honesto, sem fingir
        if ok_results:
            parts = [f"**{self.spec['title']}** processou '{instruction[:80]}' com "
                     f"{len(ok_results)} ferramenta(s): {', '.join(ok_results)}."]
            if "tool_results" in ok_results or "web_search" in ok_results:
                ws = ok_results.get("web_search") or {}
                out = ws.get("output") if isinstance(ws, dict) else None
                if isinstance(out, dict) and out.get("results"):
                    top = out["results"][0]
                    parts.append(f"Principal achado: {top.get('title', '')[:100]}")
            parts.append("Síntese completa disponível quando um modelo LLM estiver "
                         "configurado (GEMINI_API_KEY).")
            return " ".join(parts)
        return (f"**{self.spec['title']}** recebeu '{instruction[:80]}' mas as "
                f"suas ferramentas ({', '.join(self.spec['tools'])}) estão "
                f"indisponíveis. Sugestão: verificar dependências.")

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        ok = result.success and bool((result.output or {}).get("synthesis"))
        return VerificationResult(passed=ok,
                                  checks=[{"name": "has_synthesis", "passed": ok}],
                                  notes=f"agente {self.role}")


class AgentFactory:
    """Cria e regista agentes especializados no registry do FRIDAY."""

    def __init__(self, registry, llm_client=None, logger=None):
        self.registry = registry
        self.llm_client = llm_client
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))
        self.created: list[str] = []

    def create(self, role: str) -> str | None:
        spec = ROLE_SPECS.get(role)
        if spec is None:
            self.logger(f"[agent_factory] papel desconhecido: {role}", level="warn")
            return None
        name = f"agent_{role}"
        if self.registry.get(name) is not None:
            return name
        agent = _SpecialistAgent(role, spec, self.registry,
                                 self.llm_client, self.logger)
        self.registry.register(Capability(
            name=name,
            category=CapabilityCategory.AGENT,
            description=agent.description,
            impl=agent,
            tags=["agent", "specialist", role],
        ))
        self.created.append(name)
        self.logger(f"[agent_factory] agente criado: {name} ({spec['title']})")
        return name

    def create_all_defaults(self) -> list[str]:
        created = []
        for role in ROLE_SPECS:
            name = self.create(role)
            if name:
                created.append(name)
        return created

    def list_available_roles(self) -> list[dict[str, str]]:
        return [{"role": r, "title": s["title"], "goal": s["goal"],
                 "tools": ", ".join(s["tools"])}
                for r, s in ROLE_SPECS.items()]
