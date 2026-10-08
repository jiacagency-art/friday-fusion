# JIAC FRIDAY — friday-fusion

> **Tu defines o objetivo. O FRIDAY descobre como chegar lá, executa, observa, verifica, corrige e continua até terminar.**

`friday-fusion` é o laboratório inicial do JIAC FRIDAY — onde se transformam Browser Use, JEV, OWL, OpenHands, Agent-Reach, Raven, Google ADK, AutoGen, CrewAI, LangGraph, smolagents, Camel e outras tecnologias num **único sistema operacional de agentes**.

---

## Estado actual (v0.2)

✅ **Funciona end-to-end** com capabilities gratuitas (sem chaves de API):
- Web Search via DuckDuckGo
- Document generation (Markdown / JSON / TXT)
- Memory System (SQLite, 4 namespaces)
- State Engine (SQLite, retomável)
- Universal Router baseado em regras
- Execution Engine com retry + verify
- Recovery Engine com backoff

✅ **LLM Router com Gemini** (com fallback gracioso para regras):
- `GeminiClient` via endpoint OpenAI-compatible do Google
- `LLMObjectiveParser` — NL→Objective via Gemini
- `LLMRouter` — Objective→Plan via Gemini
- Auto-fallback se quota excedida, geo-block, ou sem chave

🔌 **10 engines externos suportados** (em `engines/` — clonar separadamente):

| Engine | Source | Como activar |
|--------|--------|--------------|
| browser-use | github.com/browser-use/browser-use | `pip install -e engines/browser-use` + LLM + Playwright |
| owl | github.com/camel-ai/owl | `pip install -e engines/owl` + LLM |
| openhands | github.com/All-Hands-AI/OpenHands | `pip install -e engines/openhands` + Docker |
| google-adk | github.com/google/adk-python | `pip install -e engines/google-adk` + GEMINI_API_KEY |
| autogen | github.com/microsoft/autogen | `pip install -e engines/autogen` + LLM |
| crewai | github.com/crewAIInc/crewAI | `pip install -e engines/crewai` + LLM |
| langgraph | github.com/langchain-ai/langgraph | `pip install -e engines/langgraph` + LLM |
| smolagents | github.com/huggingface/smolagents | `pip install -e engines/smolagents` + LLM |
| camel | github.com/camel-ai/camel | `pip install -e engines/camel` + LLM |
| anthropic-quickstarts | github.com/anthropics/anthropic-quickstarts | `pip install anthropic` + ANTHROPIC_API_KEY + Docker |

🚧 **19 capabilities registadas** (2 funcionais + 10 adapters externos + 7 stubs JIAC)

---

## Estrutura

```
friday-fusion/
├── friday_core/                # Núcleo do FRIDAY
│   ├── types.py                # Objective, Plan, Step, Task, Capability, ...
│   ├── objective_parser.py     # NL → Objective (regras)
│   ├── llm_objective_parser.py # NL → Objective (Gemini + fallback)
│   ├── router.py               # Universal Router: Objective → Plan (regras)
│   ├── llm_router.py           # LLM Router: Objective → Plan (Gemini + fallback)
│   ├── registry.py             # Capability Registry central
│   ├── default_registry.py     # Regista todas as 19 capabilities
│   ├── execution.py            # Execution Engine (verify + recover + retry)
│   ├── memory.py               # Memory System (USER/COMPANY/TASK/SYSTEM)
│   ├── state.py                # State Engine (SQLite, retomável)
│   ├── llm_client.py           # GeminiClient
│   └── orchestrator.py         # Friday — ponto de entrada único
│
├── capabilities/               # Implementações concretas
│   ├── web_search.py           # ✅ DuckDuckGo (sem API key)
│   ├── document_create.py      # ✅ Markdown/JSON/TXT
│   ├── browser_use_adapter.py  # Adapter p/ Browser Use
│   ├── external_adapters.py    # Adapters p/ OWL, OpenHands, ADK, AutoGen, etc.
│   └── jiac_stubs.py           # Stubs JEV/Agent-Reach/Raven/PersonalJarvis/nanoMuse/...
│
├── engines/                    # Engines externos (clonar separadamente)
│   └── README.md               # Instruções de clonagem
│
├── examples/
│   ├── demo_search_angola.py   # Demo que funciona sem API keys
│   └── demo_llm_router.py      # Demo com LLM router (mostra fallback)
│
├── tests/
│   └── (a preencher)
│
├── .env.example                # Template de configuração
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Quickstart

### Pré-requisitos
- Python 3.10+
- `httpx` (`pip install httpx`)

### Instalação

```bash
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion
pip install -r requirements.txt
```

### Configurar LLM (opcional)

```bash
cp .env.example .env
# Editar .env e preencher GEMINI_API_KEY=...
```

Sem chave: o FRIDAY usa planner de regras (funciona na mesma).
Com chave: o FRIDAY usa Gemini para parse + routing.

### Correr os demos

```bash
# Demo básico (pesquisa + relatório)
python examples/demo_search_angola.py

# Demo com LLM router (mostra fallback a funcionar)
python examples/demo_llm_router.py
```

### Usar o FRIDAY programaticamente

```python
from friday_core import Friday

friday = Friday(work_dir="friday_workspace")
task = friday.run("pesquisa empresas de IA em Angola e prepara lista comercial")

# Ver estado
print(friday.status(task.id))

# Retomar tarefa interrompida
friday.resume(task.id)

# Listar capabilities
print(friday.capabilities())
```

---

## Arquitectura

```
                  ┌─────────────────┐
   Utilizador ──► │     FRIDAY      │
                  │  (Orchestrator) │
                  └────────┬────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ObjectiveParser  Router       ExecutionEngine
         (LLM ou regras)  (LLM ou     (Plan → Results)
                          regras)        │
                                  ┌───────┴───────┐
                                  ▼               ▼
                              CapabilityRegistry  Memory+State
                              (19 caps)           (SQLite)
                                  │
        ┌──────┬──────┬─────┬─────┼─────┬───────┬───────┐
        ▼      ▼      ▼     ▼     ▼     ▼       ▼       ▼
     web_srch docs  browser owl  openhands adk  autogen crewai
     (✅DDG) (✅MD)  (adp)  (adp) (adp)   (adp) (adp)   (adp)

     + langgraph, smolagents, camel, anthropic_cua
     + 7 stubs JIAC (JEV, Agent-Reach, Raven, PersonalJarvis, nanoMuse, Android, Computer)
```

---

## Capacidades registadas (19)

### Funcionais (✅)
| Nome                  | Categoria   | Descrição                                |
|-----------------------|-------------|------------------------------------------|
| `web_search`          | research    | DuckDuckGo, sem API key                  |
| `documents_create`    | documents   | Markdown / JSON / TXT                    |

### Adapters para engines externos (🔌)
| Nome                       | Engine              | Como activar                         |
|----------------------------|---------------------|--------------------------------------|
| `browser_use`              | browser-use         | `pip install -e engines/browser-use` + LLM |
| `research_owl`             | owl                 | `pip install -e engines/owl` + LLM   |
| `coding_openhands`         | openhands           | `pip install -e engines/openhands` + Docker |
| `adk_agent`                | google-adk          | `pip install -e engines/google-adk` + GEMINI_API_KEY |
| `autogen_conversation`     | autogen             | `pip install -e engines/autogen` + LLM |
| `crewai_crew`              | crewai              | `pip install -e engines/crewai` + LLM |
| `langgraph_workflow`       | langgraph           | `pip install -e engines/langgraph` + LLM |
| `smolagents_code`          | smolagents          | `pip install -e engines/smolagents` + LLM |
| `camel_roleplay`           | camel               | `pip install -e engines/camel` + LLM |
| `computer_cua_anthropic`   | anthropic-quickstarts | `pip install anthropic` + ANTHROPIC_API_KEY + Docker |

### Stubs JIAC (🚧)
| Nome                       | Projecto JIAC        |
|----------------------------|----------------------|
| `browser_jev`              | JEV                  |
| `business_prospect`        | Agent-Reach          |
| `workflow_orchestrate`     | Raven                |
| `personal_context`         | PersonalJarvis       |
| `personal_assistant`       | nanoMuse (GPL-3.0 ⚠️) |
| `android_action`           | Android Engine (CUA/ARTEMIS) |
| `computer_action`          | Computer Engine (CUA) |

---

## LLM Router (Gemini)

O FRIDAY usa Gemini para:
1. **Objective parsing**: extrair intent + entities de pedidos em linguagem natural
2. **Routing**: decidir que capabilities usar e em que ordem

### Funcionamento

- Se `GEMINI_API_KEY` está configurada → usa LLM
- Se Gemini falha (quota, geo-block, rede) → **fallback automático** para regras
- O fallback é transparente — o utilizador não precisa de fazer nada

### Configuração

```bash
# .env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-pro-preview
```

---

## Clonar engines externos

Os engines em `engines/` são clonados separadamente para evitar aumentar o repositório. Para clonar todos:

```bash
cd engines
git clone --depth 1 https://github.com/browser-use/browser-use.git
git clone --depth 1 https://github.com/camel-ai/owl.git
git clone --depth 1 https://github.com/All-Hands-AI/OpenHands.git
git clone --depth 1 https://github.com/google/adk-python.git google-adk
git clone --depth 1 https://github.com/microsoft/autogen.git
git clone --depth 1 https://github.com/crewAIInc/crewAI.git crewai
git clone --depth 1 https://github.com/langchain-ai/langgraph.git
git clone --depth 1 https://github.com/huggingface/smolagents.git
git clone --depth 1 https://github.com/camel-ai/camel.git
git clone --depth 1 https://github.com/anthropics/anthropic-quickstarts.git
```

---

## Substituir os stubs JIAC

Cada stub em `capabilities/jiac_stubs.py` herda de `_BaseStub` e está marcado `health=False`. Para activar:

1. Criar `capabilities/<nome>_real.py` com implementação que herda de `CapabilityImpl`
2. Substituir a entrada correspondente em `friday_core/default_registry.py`
3. Garantir que `health()` retorna `True` quando pronto

---

## Roadmap

### v0.1 (✅)
- Core: Objective Parser, Router, Executor, Memory, State
- 2 capabilities funcionais (web_search, documents_create)
- 3 adapters (Browser Use, OWL, OpenHands)
- 7 stubs JIAC

### v0.2 (✅)
- LLM Router com Gemini + fallback gracioso
- +7 engines externos suportados (Google ADK, AutoGen, CrewAI, LangGraph, smolagents, Camel, Anthropic CUA)
- 19 capabilities registadas no total

### v0.3 (próximo)
- [ ] Activar Browser Use com Playwright (LLM-driven browser automation)
- [ ] Activar Google ADK (agentes Gemini com tools)
- [ ] Verification Engine mais rico (schema validation por capability)
- [ ] Recovery Engine com estratégias diferentes por tipo de erro
- [ ] Permission System (READ/ANALYZE/PREPARE/EXECUTE/CRITICAL)

### v0.4
- [ ] Scheduler (cron-like) para tarefas recorrentes
- [ ] Self-Improvement loop (detectar capability gaps)
- [ ] Learning from failures (memória de erros + recovery strategies)
- [ ] Multi-tenant isolation real

### v1.0
- [ ] Website Factory end-to-end
- [ ] Software Factory end-to-end
- [ ] Autonomia longa (8h+ sem intervenção)
- [ ] nanoMuse reescrito sem GPL (para versão proprietária)
- [ ] JEV, Agent-Reach, Raven, PersonalJarvis reais

---

## Licenças

- **friday-fusion código próprio**: MIT (JIAC AGENCY)
- **browser-use**: MIT
- **owl**: Apache-2.0
- **openhands**: MIT
- **google-adk**: Apache-2.0
- **autogen**: MIT
- **crewai**: MIT
- **langgraph**: MIT
- **smolagents**: Apache-2.0
- **camel**: Apache-2.0
- **anthropic-quickstarts**: MIT
- **nanoMuse** (não incluído, stub apenas): GPL-3.0 ⚠️
  - Não pode ser misturado em versão proprietária sem cumprir GPL
  - Para produto comercial: reimplementar as capacidades sem usar o código GPL

---

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
