# JIAC FRIDAY — Estado Actual

> Última actualização: 2026-10-08
> Versão: v0.3.1
> Repo: https://github.com/jiacagency-art/friday-fusion

---

## Resumo Executivo

O JIAC FRIDAY tem **4 capabilities fully healthy** e **15 instaladas mas com dependências em falta** (LLM keys, Docker, etc.). O sistema funciona end-to-end com fallback gracioso — quando um engine real falha, cai para uma alternativa mais simples.

**Limitação actual**: o ambiente sandbox tem Gemini com quota esgotada e sem `OPENAI_API_KEY`/`TAVILY_API_KEY`, o que impede os engines LLM-driven de funcionar. Em produção (com chaves válidas), todos os engines reais activam automaticamente.

---

## Estado das 19 Capabilities

### ✅ Healthy (4) — funcionam sem dependências extra
| Capability | Engine | Notas |
|---|---|---|
| `browser_use` | Browser Use + Playwright | ✅ Chromium instalado; só precisa LLM para executar |
| `documents_create` | (implementação própria) | ✅ Markdown/JSON/TXT |
| `crewai_crew` | CrewAI | ✅ Instalado; só precisa LLM para executar |
| `langgraph_workflow` | LangGraph | ✅ Instalado |

### 🔌 Instalados mas requerem chaves (4)
| Capability | Engine | O que falta |
|---|---|---|
| `web_search` (GPT-Researcher) | gpt-researcher | `OPENAI_API_KEY` + `TAVILY_API_KEY` |
| `research_owl` | OWL | LLM API key |
| `smolagents_code` | smolagents | `GEMINI_API_KEY` com quota |
| `adk_agent` | Google ADK | API varia por versão |

### 🔌 Instalados mas requerem Docker (2)
| Capability | Engine | O que falta |
|---|---|---|
| `coding_openhands` | OpenHands | Docker daemon |
| `computer_cua_anthropic` | Anthropic CUA | `ANTHROPIC_API_KEY` + Docker |

### 🚧 Stubs JIAC (7) — interfaces prontas, sem implementação
| Capability | Projecto JIAC |
|---|---|
| `browser_jev` | JEV |
| `business_prospect` | Agent-Reach |
| `workflow_orchestrate` | Raven |
| `personal_context` | PersonalJarvis |
| `personal_assistant` | nanoMuse (GPL-3.0) |
| `android_action` | Android Engine (CUA/ARTEMIS) |
| `computer_action` | Computer Engine (CUA) |

### 🔌 Outros adapters (2)
| Capability | Estado |
|---|---|
| `autogen_conversation` | Instalado, API varia (0.2 vs 0.4) |
| `camel_roleplay` | Instalado, API rich |

---

## Componentes Core

| Componente | Estado | Notas |
|---|---|---|
| Objective Parser | ✅ | Regras + LLM (Gemini) com fallback |
| Universal Router | ✅ | Regras + LLM com fallback |
| LLM Router | ✅ | Gemini via endpoint OpenAI-compatible |
| Execution Engine | ✅ | Retry + Verify + Recovery |
| Memory System | ✅ | Mem0 (semântico) + SQLite (fallback) |
| State Engine | ✅ | SQLite, retomável |
| Capability Registry | ✅ | 19 capabilities |
| Scheduler | ✅ | APScheduler em background |
| Self-Improvement | ✅ | Avaliação + lições aprendidas |
| Orchestrator | ✅ | Ponto de entrada único |

---

## Dependências Instaladas

```
apscheduler==3.11.2       ✅
browser-use (latest)      ✅
crewai==1.15.25           ✅
gpt-researcher (latest)   ✅ (requer OPENAI_API_KEY + TAVILY_API_KEY)
mem0ai==2.2.1             ✅ (requer OPENAI_API_KEY)
playwright (latest)       ✅
httpx                     ✅
```

Chromium instalado via `playwright install chromium`.

---

## Variáveis de Ambiente

### Necessárias (pelo menos uma)
```bash
GEMINI_API_KEY=...          # Para LLM router (com quota disponível)
OPENAI_API_KEY=...          # Para GPT-Researcher, Mem0, Browser Use alternativo
```

### Para activar engines específicos
```bash
TAVILY_API_KEY=...          # Para GPT-Researcher search
ANTHROPIC_API_KEY=...       # Para Computer Use
```

### Opcionais
```bash
GEMINI_MODEL=gemini-3.1-pro-preview
```

---

## O que FALTA FAZER

### Bloqueado por chaves/Docker (não depende de código)
- [ ] GPT-Researcher: precisa `OPENAI_API_KEY` + `TAVILY_API_KEY`
- [ ] Mem0 semântico: precisa `OPENAI_API_KEY`
- [ ] OpenHands: precisa Docker
- [ ] Anthropic CUA: precisa Docker + `ANTHROPIC_API_KEY`
- [ ] Browser Use runtime: precisa Gemini com quota OU `OPENAI_API_KEY`

### FASE 5 — Coding Engine Real
- [ ] Implementar coding capability com smolagents (não precisa Docker)
- [ ] Testar: "Cria uma app Python de gestão de contactos"

### FASE 8 — Integração Completa
- [ ] Loop end-to-end com CrewAI (3 agentes) a funcionar
- [ ] Testar objective complexo completo
- [ ] Quando chaves disponíveis, o FRIDAY deve executar tudo sozinho

### Melhorias futuras
- [ ] Permission System (READ/ANALYZE/PREPARE/EXECUTE/CRITICAL)
- [ ] Multi-tenant isolation real
- [ ] Website Factory end-to-end
- [ ] Software Factory end-to-end
- [ ] Autonomia longa (8h+ sem intervenção)
- [ ] JEV, Agent-Reach, Raven, PersonalJarvis reais

---

## Como Testar

```bash
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion
pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env
# Editar .env com chaves API

python examples/demo_search_angola.py        # Pesquisa básica
python examples/demo_llm_router.py           # Com LLM router
python examples/demo_scheduler.py            # Scheduler
python examples/demo_self_improvement.py     # Self-improvement
python examples/demo_integration.py          # Integração completa
```

---

## Notas Técnicas

### Gemini API (2026-10)
- Modelos `gemini-2.0/2.5` foram descontinuados
- `gemini-3.1-pro-preview` funciona mas free tier tem quota muito limitada
- `gemini-3.8-flash` tem geo-block em algumas regiões
- Fallback gracioso: se Gemini falhar, usa regras

### GPT-Researcher
- Requer `OPENAI_API_KEY` (não funciona com Gemini directamente)
- Requer `TAVILY_API_KEY` para search retriever
- Sem estas chaves, faz fallback para DuckDuckGo

### Mem0
- Requer `OPENAI_API_KEY` (usa OpenAI para extracção de factos)
- Fallback gracioso para SQLite quando indisponível

### Browser Use
- Requer LLM para decidir cada acção no browser
- Chromium instalado via `playwright install chromium`
- Sem LLM disponível, `health()=False`

### Self-Improvement
- Implementação própria (avaliação por regras + heurísticas)
- Avalia cada task: score (0-100), failures, recoveries
- Classifica erros: timeout, missing_dependency, stub_not_implemented, rate_limit, network, unknown
- Guarda lições em `MemoryNS.SYSTEM` → key `lessons_learned`

### Scheduler
- APScheduler BackgroundScheduler
- 3 jobs default: 08:00 mercado, 17:00 leads, dom 10:00 análise semanal
- Corre em thread separado, não bloqueia orchestrator

---

## Arquitectura v0.3.1

```
                  ┌─────────────────────┐
   Utilizador ──► │       FRIDAY        │
                  │   (Orchestrator)    │
                  └──────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ObjectiveParser      Router (LLM/reg)    ExecutionEngine
   (LLM/reg)                │                (retry+verify+recover)
                            │                        │
                    ┌───────┴───────┐        ┌───────┴───────┐
                    ▼               ▼        ▼               ▼
              CapabilityRegistry   Memory    State         Scheduler
              (19 caps, 4 healthy) (Mem0/   (SQLite)     (APScheduler)
                                    SQLite)
                            │
        ┌───────┬───────┬───┴───┬───────┬───────┐
        ▼       ▼       ▼       ▼       ▼       ▼
     Browser  CrewAI  Docs   LangGraph  GPT-Res  Stubs
     Use(✅) (✅)   (✅)  (✅)    (🔌)   JIAC(7)
                                      │
                              Self-Improvement Engine
                              (avalia cada task,
                               extrai lições,
                               regista recoveries)
```

---

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
