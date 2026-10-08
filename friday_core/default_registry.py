"""Default Registry — regista todas as capabilities do FRIDAY."""

from __future__ import annotations
from pathlib import Path
from friday_core.registry import CapabilityRegistry
from friday_core.types import Capability, CapabilityCategory, RiskLevel
from capabilities.web_search import WebSearchCapability
from capabilities.document_create import DocumentCreateCapability
from capabilities.browser_use_adapter import BrowserUseAdapter
from capabilities.external_adapters import (
    OWLAdapter, OpenHandsAdapter, GoogleADKAdapter, AutoGenAdapter,
    CrewAIAdapter, LangGraphAdapter, SmolagentsAdapter, CamelAdapter,
    AnthropicCUAAdapter,
)
from capabilities.jiac_stubs import (
    JEVAdapter, AgentReachAdapter, RavenAdapter, PersonalJarvisAdapter,
    NanoMuseAdapter, AndroidEngineAdapter, ComputerEngineAdapter,
)


def build_default_registry(output_dir: str | Path = "outputs") -> CapabilityRegistry:
    r = CapabilityRegistry()

    # Research
    r.register(Capability(
        name="web_search", category=CapabilityCategory.RESEARCH,
        description="Pesquisa web via DuckDuckGo (sem API key)",
        impl=WebSearchCapability(), tags=["search", "duckduckgo", "free"],
    ))
    r.register(Capability(
        name="research_owl", category=CapabilityCategory.RESEARCH,
        description="OWL — research agent multi-turno",
        impl=OWLAdapter(), tags=["deep_research", "owl"],
    ))

    # Browser
    r.register(Capability(
        name="browser_use", category=CapabilityCategory.BROWSER,
        description="Browser Use — agente autónomo de navegador",
        impl=BrowserUseAdapter(), tags=["browser", "automation"],
    ))
    r.register(Capability(
        name="browser_jev", category=CapabilityCategory.BROWSER,
        description="JEV — JIAC browser engine (stub)",
        impl=JEVAdapter(), tags=["browser", "jiac", "stub"],
    ))

    # Coding
    r.register(Capability(
        name="coding_openhands", category=CapabilityCategory.CODING,
        description="OpenHands — agente de engenharia de software",
        impl=OpenHandsAdapter(), tags=["coding", "engineering"],
    ))
    r.register(Capability(
        name="smolagents_code", category=CapabilityCategory.CODING,
        description="HuggingFace smolagents — code-based agents",
        impl=SmolagentsAdapter(), tags=["code_agent", "huggingface"],
    ))

    # Business
    r.register(Capability(
        name="business_prospect", category=CapabilityCategory.BUSINESS,
        description="Agent-Reach — prospecção comercial (stub)",
        impl=AgentReachAdapter(), tags=["sales", "b2b", "stub"],
    ))

    # Android
    r.register(Capability(
        name="android_action", category=CapabilityCategory.ANDROID,
        description="Android Engine — CUA/ARTEMIS (stub)",
        impl=AndroidEngineAdapter(), tags=["android", "mobile", "stub"],
    ))

    # Computer
    r.register(Capability(
        name="computer_action", category=CapabilityCategory.COMPUTER,
        description="Computer Engine — CUA desktop (stub)",
        impl=ComputerEngineAdapter(), tags=["desktop", "os", "stub"],
    ))
    r.register(Capability(
        name="personal_context", category=CapabilityCategory.COMPUTER,
        description="PersonalJarvis — memória pessoal (stub)",
        impl=PersonalJarvisAdapter(), tags=["memory", "personal", "stub"],
    ))
    r.register(Capability(
        name="computer_cua_anthropic", category=CapabilityCategory.COMPUTER,
        description="Anthropic Computer Use — controla desktop via Claude",
        impl=AnthropicCUAAdapter(), tags=["cua", "desktop", "anthropic"],
    ))

    # Documents
    r.register(Capability(
        name="documents_create", category=CapabilityCategory.DOCUMENTS,
        description="Gera documentos Markdown / JSON / TXT",
        impl=DocumentCreateCapability(output_dir=output_dir),
        tags=["docs", "report"],
    ))

    # Internal
    r.register(Capability(
        name="workflow_orchestrate", category=CapabilityCategory.INTERNAL,
        description="Raven — orquestração de workflows complexos (stub)",
        impl=RavenAdapter(), tags=["orchestration", "stub"],
    ))
    r.register(Capability(
        name="personal_assistant", category=CapabilityCategory.INTERNAL,
        description="nanoMuse — agente pessoal (GPL-3.0, stub)",
        impl=NanoMuseAdapter(), tags=["personal", "gpl", "stub"],
    ))
    r.register(Capability(
        name="adk_agent", category=CapabilityCategory.INTERNAL,
        description="Google ADK — constrói agentes via Gemini",
        impl=GoogleADKAdapter(), tags=["gemini", "google", "agent_builder"],
    ))
    r.register(Capability(
        name="autogen_conversation", category=CapabilityCategory.INTERNAL,
        description="Microsoft AutoGen — multi-agent conversation",
        impl=AutoGenAdapter(), tags=["multi_agent", "microsoft"],
    ))
    r.register(Capability(
        name="crewai_crew", category=CapabilityCategory.INTERNAL,
        description="CrewAI — role-based multi-agent crews",
        impl=CrewAIAdapter(), tags=["multi_agent", "role_based"],
    ))
    r.register(Capability(
        name="langgraph_workflow", category=CapabilityCategory.INTERNAL,
        description="LangGraph — stateful agent graphs",
        impl=LangGraphAdapter(), tags=["graph", "stateful"],
    ))
    r.register(Capability(
        name="camel_roleplay", category=CapabilityCategory.INTERNAL,
        description="Camel-AI — role-playing multi-agent",
        impl=CamelAdapter(), tags=["roleplay", "multi_agent"],
    ))

    return r
