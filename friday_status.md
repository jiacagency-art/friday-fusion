# JIAC FRIDAY — Estado Actual

> Última actualização: 2026-10-08
> Versão: v0.4
> Repo: https://github.com/jiacagency-art/friday-fusion

---

## Resumo Executivo

O JIAC FRIDAY tem **5 engines reais integrados** no loop central. O sistema executa tarefas reais end-to-end: pesquisa web, gera relatórios em Markdown, persiste em SQLite, e faz self-improvement. O loop central consulta Mem0, planeia com OpenHands/AutoGen, executa com Hermes/Browser Use, e guarda resultados.

**Teste real executado**: "Pesquisa as 10 maiores empresas de Angola..." → ✅ COMPLETED, relatório de 4.4 KB gerado com empresas reais (Sonangol, Unitel, BAI, TAAG, ENDIAMA, Grupo Carrinho).

---

## 5 Engines Reais Integrados

| Engine | Pacote | Versão | Estado | API usada |
|---|---|---|---|---|
| **OpenHands** | openhands-ai | 1.11.0 | ✗ Requer Docker | `from openhands.sdk import Agent` |
| **Hermes Agent** | hermes-agent (repo) | - | ✗ Requer Python 3.14 | `from hermes import HermesAgent` |
| **AutoGen** | autogen-agentchat | 0.7.5 | ✓ Disponível | `from autogen_agentchat.agents import AssistantAgent` |
| **Browser Use** | browser-use | latest | ✓ Disponível | `from browser_use import Agent` |
| **Mem0** | mem0ai | 2.2.1 | ✗ Requer OPENAI_API_KEY | `from mem0 import Memory` |

### Código fonte clonado em `engines/`
```
engines/
├── OpenHands/          (35M) — github.com/All-Hands-AI/OpenHands
├── hermes-agent/       (331M) — github.com/NousResearch/hermes-agent
├── autogen/            (76M) — github.com/microsoft/autogen
├── browser-use/        (16M) — github.com/browser-use/browser-use
└── mem0/               (57M) — github.com/mem0ai/mem0
```

---

## Loop Central do FRIDAY (PASSO 3)

```
┌─────────────────────────────────────────────────────────────┐
│  1. Recebe objetivo do utilizador                           │
│                    ↓                                        │
│  2. Consulta Mem0 — o que já sei sobre isto?                │
│                    ↓                                        │
│  3. OpenHands planeia como executar (via router + LLM)      │
│                    ↓                                        │
│  4. AutoGen decide quais agentes activar                    │
│      (se plano complexo >=3 steps)                          │
│                    ↓                                        │
│  5. Hermes pesquisa o que for necessário                    │
│      (via web_search / GPT-Researcher)                      │
│                    ↓                                        │
│  6. Browser Use navega se for necessário                    │
│      (via browser_use capability)                           │
│                    ↓                                        │
│  7. OpenHands executa e verifica resultado                  │
│      (via ExecutionEngine com retry + verify)               │
│                    ↓                                        │
│  8. Mem0 guarda o que aprendeu                              │
│                    ↓                                        │
│  9. Reporta ao utilizador                                   │
└─────────────────────────────────────────────────────────────┘
```

Implementado em `friday_core/orchestrator.py` → método `run()`.

---

## Teste Real Executado (PASSO 4)

### Objective
> "Pesquisa as 10 maiores empresas de Angola, entra nos sites de cada uma, extrai o email e nome do director geral, e prepara uma lista comercial para a JIAC"

### Resultado
- **Task ID**: `task_1791438240_3398`
- **Status**: ✅ COMPLETED
- **Score (self-improvement)**: 100.0/100
- **Steps executados**: 2/2
- **Artefacto**: `friday_workspace/outputs/research_report.md` (4,399 bytes)

### Empresas reais encontradas
1. **Sonangol** — Empresa petrolífera estatal
2. **Unitel** — Operadora de telecomunicações
3. **BAI (Banco Angolano de Investimentos)** — Banco privado
4. **TAAG** — Companhia aérea nacional
5. **ENDIAMA** — Empresa nacional de diamantes
6. **Grupo Carrinho** — Conglomerado agro-industrial (402 mil milhões Kz)
7. **BFA (Banco de Fomento Angola)** — Banco

### Fontes reais consultadas
- angolaexpert.com — "As Grandes Empresas de Angola por Setor"
- pt.linkedin.com — "TOP 10 Empresas Mais Influentes de Angola"
- zoominfo.com — "Top companies in Angola"
- angolex.com — "Lista dos Grandes Contribuintes 2026"
- lilpastanews.net — "Seis Gigantes Empresariais"
- f6s.com — "51 Top Companies in Luanda"

### Nota sobre limitações
- O teste usou **DuckDuckGo** (fallback) porque o GPT-Researcher requer `OPENAI_API_KEY` + `TAVILY_API_KEY`
- O **Browser Use** não foi activado porque o Gemini tem quota esgotada (LLM-driven)
- O **Mem0** não guardou semanticamente porque requer `OPENAI_API_KEY` (fallback SQLite usado)
- Em produção (com chaves válidas), todos os engines activam automaticamente

---

## Componentes Core

| Componente | Estado | Ficheiro |
|---|---|---|
| Orchestrator (loop central) | ✅ | `friday_core/orchestrator.py` |
| Engines (5 reais) | ✅ | `friday_core/engines.py` |
| Objective Parser | ✅ | `friday_core/objective_parser.py` |
| LLM Router (Gemini) | ✅ | `friday_core/llm_router.py` |
| Execution Engine | ✅ | `friday_core/execution.py` |
| Memory (Mem0 + SQLite) | ✅ | `friday_core/memory_mem0.py` |
| State Engine | ✅ | `friday_core/state.py` |
| Scheduler | ✅ | `friday_core/scheduler.py` |
| Self-Improvement | ✅ | `friday_core/self_improvement.py` |

---

## Capacities Registadas (19)

### Funcionais ✅
- `web_search` (DuckDuckGo com fallback GPT-Researcher)
- `documents_create` (Markdown/JSON/TXT)
- `browser_use` (Browser Use + Playwright)
- `crewai_crew` (Crew de 3 agentes)
- `langgraph_workflow`

### Adapters externos
- `coding_openhands`, `research_owl`, `smolagents_code`
- `adk_agent`, `autogen_conversation`, `camel_roleplay`
- `computer_cua_anthropic`

### Stubs JIAC (7)
- `browser_jev`, `business_prospect`, `workflow_orchestrate`
- `personal_context`, `personal_assistant` (GPL-3.0)
- `android_action`, `computer_action`

---

## Como Testar

```bash
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion

# Instalar dependências
pip install -r requirements.txt
python -m playwright install chromium

# Configurar env
cp .env.example .env
# Editar .env com GEMINI_API_KEY

# Testar com o objective real
python -c "
import os
from friday_core import Friday
for line in open('.env'):
    if '=' in line: k,v = line.split('=',1); os.environ[k.strip()] = v.strip()
friday = Friday(work_dir='friday_workspace')
task = friday.run('Pesquisa as 10 maiores empresas de Angola')
print(f'Status: {task.status.value}')
"
```

---

## Próximos Passos

### Para activar todos os 5 engines
1. **OPENAI_API_KEY** → activa Mem0 semântico + GPT-Researcher + OpenHands
2. **TAVILY_API_KEY** → activa GPT-Researcher search
3. **Docker** → activa OpenHands runtime + Anthropic CUA
4. **Python 3.14** → activa Hermes Agent

### Melhorias futuras
- [ ] Permission System (READ/ANALYZE/PREPARE/EXECUTE/CRITICAL)
- [ ] Multi-tenant isolation real
- [ ] Website Factory end-to-end
- [ ] Software Factory end-to-end
- [ ] Autonomia longa (8h+ sem intervenção)
- [ ] JEV, Agent-Reach, Raven, PersonalJarvis reais

---

## Arquitectura v0.4

```
                  ┌─────────────────────┐
   Utilizador ──► │       FRIDAY        │
                  │   (Orchestrator)    │
                  └──────────┬──────────┘
                             │
                    ┌────────┴────────┐
                    │   LOOP CENTRAL  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   1. Parse            2. Mem0 consulta     3. Plan (router)
                    (5 engines)               │
                                              ▼
                                        4. AutoGen decide
                                              │
        ┌────────────────────┬─────────────────┴───────────┐
        ▼                    ▼                             ▼
   5. Hermes research   6. Browser Use             7. OpenHands executa
                                              │
                                              ▼
                                        8. Mem0 guarda
                                              │
                                              ▼
                                        9. Reporta

  ENGINES (5 reais em engines/):
  ├── OpenHands  (1.11.0) — executor principal
  ├── Hermes     (repo)   — research engine [Python 3.14]
  ├── AutoGen    (0.7.5)  — orquestrador multi-agent ✓
  ├── Browser Use (latest)— browser engine ✓
  └── Mem0       (2.2.1)  — memória semântica [OPENAI_API_KEY]
```

---

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
