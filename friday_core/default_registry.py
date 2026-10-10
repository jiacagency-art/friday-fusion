"""Default Registry — regista todas as capabilities do FRIDAY (v1.0 REAL)."""

from __future__ import annotations
from pathlib import Path
from friday_core.registry import CapabilityRegistry
from friday_core.types import Capability, CapabilityCategory, RiskLevel


def _load_capability_classes() -> dict:
    """
    Importa TODAS as capabilities de forma lazy (dentro do builder).

    Isto evita imports circulares: capabilities importam friday_core.types,
    e o package friday_core importa capabilities — se os imports fossem
    module-level, qualquer ordem de import rebentaria.
    """
    from capabilities.web_search import WebSearchCapability
    from capabilities.document_create import DocumentCreateCapability
    from capabilities.gpt_researcher_capability import GPTResearcherCapability
    from capabilities.browser_use_adapter import BrowserUseAdapter
    from capabilities.crewai_real import CrewAICapability
    from capabilities.external_adapters import (
        OWLAdapter, OpenHandsAdapter, GoogleADKAdapter, AutoGenAdapter,
        LangGraphAdapter, SmolagentsAdapter, CamelAdapter, AnthropicCUAAdapter,
    )
    from capabilities.jiac_stubs import (
        JEVAdapter, AgentReachAdapter, RavenAdapter, PersonalJarvisAdapter,
        NanoMuseAdapter, AndroidEngineAdapter, ComputerEngineAdapter,
    )
    from capabilities.video_editor import VideoEditorCapability
    from capabilities.briefing import BriefingCapability
    from capabilities.data_analyze import DataAnalyzeCapability
    from capabilities.prospect import ProspectCapability
    from capabilities.email_send import EmailCapability

    return {
        "web_search": WebSearchCapability,
        "document_create": DocumentCreateCapability,
        "gpt_researcher": GPTResearcherCapability,
        "browser_use": BrowserUseAdapter,
        "crewai": CrewAICapability,
        "owl": OWLAdapter, "openhands": OpenHandsAdapter,
        "adk": GoogleADKAdapter, "autogen": AutoGenAdapter,
        "langgraph": LangGraphAdapter, "smolagents": SmolagentsAdapter,
        "camel": CamelAdapter, "anthropic_cua": AnthropicCUAAdapter,
        "jev": JEVAdapter, "agent_reach": AgentReachAdapter,
        "raven": RavenAdapter, "personal_jarvis": PersonalJarvisAdapter,
        "nanomuse": NanoMuseAdapter, "android": AndroidEngineAdapter,
        "computer": ComputerEngineAdapter,
        "video_editor": VideoEditorCapability,
        "briefing": BriefingCapability,
        "data_analyze": DataAnalyzeCapability,
        "prospect": ProspectCapability,
        "email": EmailCapability,
    }


def build_default_registry(output_dir: str | Path = "outputs",
                           use_gpt_researcher: bool = True) -> CapabilityRegistry:
    """
    Constrói o registry default do FRIDAY (v1.0).

    Args:
        output_dir: onde as capabilities escrevem ficheiros
        use_gpt_researcher: se True, tenta GPT-Researcher como web_search
                           (fallback automático para DuckDuckGo).
    """
    C = _load_capability_classes()
    r = CapabilityRegistry()
    out = Path(output_dir)

    # --- Research ---------------------------------------------------------
    # GPT-Researcher quando disponível; senão DuckDuckGo puro (health-based)
    if use_gpt_researcher:
        _gpt = C["gpt_researcher"]()
        research_cap = _gpt if _gpt.health() else C["web_search"]()
    else:
        research_cap = C["web_search"]()
    r.register(Capability(
        name="web_search", category=CapabilityCategory.RESEARCH,
        description="Research (GPT-Researcher → DuckDuckGo fallback, sem API keys)",
        impl=research_cap, tags=["search", "research"],
    ))
    r.register(Capability(
        name="research_owl", category=CapabilityCategory.RESEARCH,
        description="OWL — research agent multi-turno",
        impl=C["owl"](), tags=["deep_research", "owl"],
    ))

    # --- Browser ----------------------------------------------------------
    r.register(Capability(
        name="browser_use", category=CapabilityCategory.BROWSER,
        description="Browser Use — agente autónomo de navegador (REAL)",
        impl=C["browser_use"](), tags=["browser", "automation"],
    ))
    r.register(Capability(
        name="browser_jev", category=CapabilityCategory.BROWSER,
        description="JEV — JIAC browser engine (stub)",
        impl=C["jev"](), tags=["browser", "jiac", "stub"],
    ))

    # --- Coding -----------------------------------------------------------
    r.register(Capability(
        name="coding_openhands", category=CapabilityCategory.CODING,
        description="OpenHands/SWE-agent — agente de engenharia de software",
        impl=C["openhands"](), tags=["coding", "engineering"],
    ))
    r.register(Capability(
        name="smolagents_code", category=CapabilityCategory.CODING,
        description="HuggingFace smolagents — code-based agents",
        impl=C["smolagents"](), tags=["code_agent", "huggingface"],
    ))

    # --- v1.0: Video Engine ------------------------------------------------
    r.register(Capability(
        name="video_editor", category=CapabilityCategory.VIDEO,
        description="Editor de vídeo agentivo — corta, vertical/horizontal, "
                    "legendas, destaque, storyboard (ffmpeg, sem API keys)",
        impl=C["video_editor"](output_dir=out / "video"),
        risk=RiskLevel.LOW,
        tags=["video", "ffmpeg", "edit", "tiktok", "reels"],
    ))

    # --- v1.0: Briefing proativo -------------------------------------------
    r.register(Capability(
        name="briefing", category=CapabilityCategory.BUSINESS,
        description="Briefing proativo — clima + notícias + IA + agenda + "
                    "tarefas + resumo executivo (sem API keys)",
        impl=C["briefing"](output_dir=out),
        tags=["briefing", "dashboard", "proactive", "news", "weather"],
    ))

    # --- v1.0: Data Engine --------------------------------------------------
    r.register(Capability(
        name="data_analyze", category=CapabilityCategory.DATA,
        description="Data Engine — análise de CSV/JSON: perfil, estatísticas, "
                    "correlações, group-by, relatório",
        impl=C["data_analyze"](output_dir=out),
        tags=["data", "csv", "statistics", "analysis"],
    ))

    # --- v1.0: Agent-Reach REAL (prospecção comercial) -----------------------
    r.register(Capability(
        name="prospect_real", category=CapabilityCategory.BUSINESS,
        description="Agent-Reach real — pesquisa empresas, detecta "
                    "oportunidades, gera lista comercial CSV CRM",
        impl=C["prospect"](output_dir=out, web_search_impl=research_cap),
        risk=RiskLevel.LOW,
        tags=["sales", "b2b", "crm", "leads", "prospect"],
    ))

    # --- v1.0: Communication Engine (email) ----------------------------------
    r.register(Capability(
        name="email_send", category=CapabilityCategory.COMMUNICATION,
        description="Email real via SMTP (ou rascunho .eml honesto) — "
                    "requer aprovação quando envia",
        impl=C["email"](output_dir=out),
        requires_approval=True,
        risk=RiskLevel.CRITICAL,
        tags=["email", "smtp", "communication"],
    ))

    # --- Business (stub legado p/ compat) -------------------------------------
    r.register(Capability(
        name="business_prospect", category=CapabilityCategory.BUSINESS,
        description="Agent-Reach — prospecção comercial (stub legado; usar prospect_real)",
        impl=C["agent_reach"](), tags=["sales", "b2b", "stub"],
    ))

    # --- Android ----------------------------------------------------------
    r.register(Capability(
        name="android_action", category=CapabilityCategory.ANDROID,
        description="Android Engine — CUA/ARTEMIS (stub)",
        impl=C["android"](), tags=["android", "mobile", "stub"],
    ))

    # --- Computer ---------------------------------------------------------
    r.register(Capability(
        name="computer_action", category=CapabilityCategory.COMPUTER,
        description="Computer Engine — CUA desktop (stub)",
        impl=C["computer"](), tags=["desktop", "os", "stub"],
    ))
    r.register(Capability(
        name="personal_context", category=CapabilityCategory.COMPUTER,
        description="PersonalJarvis — memória pessoal (stub)",
        impl=C["personal_jarvis"](), tags=["memory", "personal", "stub"],
    ))
    r.register(Capability(
        name="computer_cua_anthropic", category=CapabilityCategory.COMPUTER,
        description="Anthropic Computer Use — controla desktop via Claude",
        impl=C["anthropic_cua"](), tags=["cua", "desktop", "anthropic"],
    ))

    # --- Documents --------------------------------------------------------
    r.register(Capability(
        name="documents_create", category=CapabilityCategory.DOCUMENTS,
        description="Gera documentos Markdown / JSON / TXT",
        impl=C["document_create"](output_dir=output_dir),
        tags=["docs", "report"],
    ))

    # --- Internal (Multi-agent) ------------------------------------------
    r.register(Capability(
        name="crewai_crew", category=CapabilityCategory.INTERNAL,
        description="CrewAI — crew de 3 agentes (Research + Browser + Report) REAL",
        impl=C["crewai"](), tags=["multi_agent", "crew", "real"],
    ))
    r.register(Capability(
        name="workflow_orchestrate", category=CapabilityCategory.INTERNAL,
        description="Raven — orquestração de workflows complexos (stub)",
        impl=C["raven"](), tags=["orchestration", "stub"],
    ))
    r.register(Capability(
        name="personal_assistant", category=CapabilityCategory.INTERNAL,
        description="nanoMuse — agente pessoal (GPL-3.0, stub)",
        impl=C["nanomuse"](), tags=["personal", "gpl", "stub"],
    ))
    r.register(Capability(
        name="adk_agent", category=CapabilityCategory.INTERNAL,
        description="Google ADK — constrói agentes via Gemini",
        impl=C["adk"](), tags=["gemini", "google", "agent_builder"],
    ))
    r.register(Capability(
        name="autogen_conversation", category=CapabilityCategory.INTERNAL,
        description="Microsoft AutoGen — multi-agent conversation",
        impl=C["autogen"](), tags=["multi_agent", "microsoft"],
    ))
    r.register(Capability(
        name="langgraph_workflow", category=CapabilityCategory.INTERNAL,
        description="LangGraph — stateful agent graphs",
        impl=C["langgraph"](), tags=["graph", "stateful"],
    ))
    r.register(Capability(
        name="camel_roleplay", category=CapabilityCategory.INTERNAL,
        description="Camel-AI — role-playing multi-agent",
        impl=C["camel"](), tags=["roleplay", "multi_agent"],
    ))

    return r
