# JIAC FRIDAY — Estado Actual

> Última actualização: 2026-10-08
> Versão: v0.3
> Repo: https://github.com/jiacagency-art/friday-fusion

---

## Resumo Executivo

O JIAC FRIDAY está funcional com **5 capabilities reais activas** (Browser Use, GPT-Researcher, CrewAI, Mem0 Memory, APScheduler) e **7 stubs JIAC** prontos para implementação. O sistema faz fallback gracioso quando engines não estão disponíveis (sem LLM, sem Docker, etc.).

---

## O que está FUNCIONAL ✅

### Core (núcleo do sistema operacional)
| Componente | Estado | Notas |
|---|---|---|
| Objective Parser | ✅ | Regras + LLM (Gemini) com fallback |
| Universal Router | ✅ | Regras + LLM com fallback |
| Execution Engine | ✅ | Retry + Verify + Recovery |
| State Engine | ✅ | SQLite, retomável |
| Capability Registry | ✅ | 19 capabilities registadas |
| Orchestrator | ✅ | Ponto de entrada único |

### Engines Reais Activados (v0.3)
| Engine | Package | Estado | Notas |
|---|---|---|---|
| Browser Use | `browser-use` + `playwright` | ✅ Instalado | LLM-driven; Chromium instalado |
| GPT-Researcher | `gpt-researcher` | ✅ Instalado | Substitui DuckDuckGo; fallback se LLM falhar |
| CrewAI | `crewai` | ✅ Instalado | Crew de 3 agentes (Research + Browser + Report) |
| Mem0 Memory | `mem0ai` | ✅ Instalado | Memória semântica; fallback SQLite se sem LLM |
| APScheduler | `apscheduler` | ✅ Instalado | Scheduler em background |
| Self-Improvement | (implementação própria) | ✅ | Avaliação de tasks + lições aprendidas |

### Capabilities Healthy (5)
1. `web_search` (GPT-Researcher com fallback DuckDuckGo)
2. `browser_use` (Browser Use + Playwright + Chromium)
3. `crewai_crew` (Crew de 3 agentes)
4. `documents_create` (Markdown/JSON/TXT)
5. `research_owl` (OWL — instalado mas requer LLM)

---

## O que está em STUB 🚧

### Stubs JIAC (7) — precisam implementação real
| Stub | Projecto JIAC | Interface pronta? |
|---|---|---|
| `browser_jev` | JEV (browser engine) | ✅ |
| `business_prospect` | Agent-Reach (prospecção) | ✅ |
| `workflow_orchestrate` | Raven (orquestração) | ✅ |
| `personal_context` | PersonalJarvis (memória pessoal) | ✅ |
| `personal_assistant` | nanoMuse (GPL-3.0 ⚠️) | ✅ |
| `android_action` | Android Engine (CUA/ARTEMIS) | ✅ |
| `computer_action` | Computer Engine (CUA) | ✅ |

### Adapters externos não activados (requerem Docker ou config extra)
| Engine | Razão |
|---|---|
| OpenHands | Requer Docker daemon |
| Anthropic CUA | Requer Docker + ANTHROPIC_API_KEY |
| Google ADK | Instalado mas API varia por versão |
| AutoGen | Instalado mas API varia (0.2 vs 0.4) |
| LangGraph | Requer definição de grafo custom |
| smolagents | Instalado mas requer config LiteLLM |
| Camel | Instalado mas API rich |

---

## O que FALTA FAZER ❌

### FASE 5 — Coding Engine Real
- [ ] Activar OpenHands (requer Docker — não disponível em sandbox)
- [ ] **Alternativa**: implementar coding capability com smolagents (não precisa Docker)
- [ ] Testar: "Cria uma aplicação Python de gestão de contactos"

### FASE 8 — Integração Completa
- [ ] Loop end-to-end: Input → Parser → Router → Crew → Execution → Verify → Self-Improve → Report
- [ ] Testar objective complexo: "análise completa do mercado angolano de energia"
- [ ] O FRIDAY deve executar tudo sozinho

### Melhorias futuras
- [ ] Permission System (READ/ANALYZE/PREPARE/EXECUTE/CRITICAL)
- [ ] Multi-tenant isolation real
- [ ] Website Factory end-to-end
- [ ] Software Factory end-to-end
- [ ] Autonomia longa (8h+ sem intervenção)
- [ ] JEV, Agent-Reach, Raven, PersonalJarvis reais

---

## Dependências Instaladas

```
apscheduler==3.11.2
browser-use (latest)
crewai==1.15.25
gpt-researcher (latest)
mem0ai==2.2.1
playwright (latest)
httpx>=0.27.0
```

Chromium instalado via `playwright install chromium`.

---

## Configuração

### Variáveis de ambiente necessárias
```bash
GEMINI_API_KEY=...          # Para LLM router, Browser Use, GPT-Researcher, CrewAI, Mem0
GEMINI_MODEL=gemini-3.1-pro-preview
```

### Opcionais
```bash
OPENAI_API_KEY=...          # Alternativa ao Gemini
ANTHROPIC_API_KEY=...       # Para Computer Use
```

---

## Como Testar

```bash
# Clone
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion

# Instalar dependências
pip install -r requirements.txt

# Configurar env
cp .env.example .env
# Editar .env com GEMINI_API_KEY

# Demos
python examples/demo_search_angola.py        # Pesquisa básica
python examples/demo_llm_router.py           # Com LLM router
python examples/demo_scheduler.py            # Scheduler
python examples/demo_self_improvement.py     # Self-improvement
```

---

## Arquitectura v0.3

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
              (19 caps, 5 healthy) (Mem0/   (SQLite)     (APScheduler)
                                    SQLite)
                            │
        ┌───────┬───────┬───┴───┬───────┬───────┐
        ▼       ▼       ▼       ▼       ▼       ▼
     GPT-Res  Browser  CrewAI  Docs   OWL    Stubs
     (✅)    Use(✅)  (✅)   (✅)  (adp)  JIAC(7)
              │
        Self-Improvement Engine
        (avalia cada task,
         extrai lições,
         regista recoveries)
```

---

## Notas Técnicas

### Gemini API
- Modelos `gemini-2.0-flash`, `gemini-2.5-flash`, `gemini-2.5-pro` foram descontinuados
- `gemini-3.1-pro-preview` funciona mas free tier tem quota limitada
- `gemini-3.8-flash` tem geo-block em algumas regiões
- Quando quota esgotada, o FRIDAY faz fallback para regras automaticamente

### Mem0
- Requer OpenAI API key (não funciona com Gemini diretamente)
- Fallback gracioso para SQLite quando indisponível
- Para activar: definir `OPENAI_API_KEY` no `.env`

### Browser Use
- Requer LLM para decidir cada acção no browser
- Chromium instalado via `playwright install chromium`
- Sem LLM disponível, `health()=False`

### Self-Improvement
- Implementação própria (não usa `reflexion` ou `self-refine` — são papers de pesquisa, não packages)
- Avalia cada task: score (0-100), failures, recoveries
- Classifica erros: timeout, missing_dependency, stub_not_implemented, rate_limit, network, unknown
- Guarda lições em `MemoryNS.SYSTEM` na key `lessons_learned`

---

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
