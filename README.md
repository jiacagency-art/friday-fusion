# JIAC FRIDAY — friday-fusion v1.0

> **Tu defines o objetivo. O FRIDAY descobre como chegar lá, executa, observa, verifica, corrige e continua até terminar.**
> *Autonomous Intelligence. Real Execution. Continuous Evolution.*
> Um projeto da **JIAC AGENCY** — "Diminuir o custo, aumentar o lucro."

`friday-fusion` é o **sistema operacional de agentes de IA** do JIAC FRIDAY — a implementação da visão completa: um núcleo central que junta Browser Use, JEV (Fast Execution), OWL, OpenHands/SWE-agent, AutoGen, CrewAI, Agent-Reach, GPT-Researcher e outros num **sistema único**, com autonomia local (funciona **sem nenhuma API key obrigatória**) e expansão por repositórios GitHub.

---

## O que há de novo na v1.0

| Sistema | Estado | Descrição |
|---|---|---|
| ⚡ **Fast Execution Fabric (JEV)** | ✅ REAL | Steps independentes executam **em paralelo** (ondas topológicas), cache de respostas, timeout por step, métricas p50/p95 |
| 🛡 **Permission System** | ✅ REAL | READ → ANALYZE → PREPARE → EXECUTE → CRITICAL; audit trail; aprovação humana obrigatória para acções críticas (email real, etc.) |
| 🔄 **Recovery Engine** | ✅ REAL | Estratégias por tipo de erro (rede → backoff, rate-limit → espera, missing cap → alternativa, quota → degrada para regras) |
| 🎬 **Video Editor Engine** | ✅ REAL | Editor de vídeo agentivo com ffmpeg: corta, vertical 9:16 (TikTok/Reels), horizontal 16:9, legendas PT, destaque com círculo animado, storyboard, GIF, extrair áudio |
| ☀️ **Briefing proativo** | ✅ REAL | Clima (wttr.in) + notícias (Google News RSS) + novidades de IA + agenda + tarefas prioritárias + resumo executivo — **sem API keys** |
| 📊 **Data Engine** | ✅ REAL | Análise de CSV/JSON: perfil por coluna, estatísticas, correlações de Pearson, group-by, relatório Markdown |
| 💼 **Agent-Reach real** | ✅ REAL | Prospecção comercial: pesquisa empresas, detecta oportunidades, exporta **lista CRM em CSV** + MD + JSON |
| ✉️ **Communication Engine** | ✅ REAL | Email SMTP real (com aprovação) ou rascunho .eml honesto quando não configurado — **nunca finge que enviou** |
| 🤖 **Agent Factory** | ✅ REAL | Cria agentes especializados on-demand: researcher, prospector, writer, analyst, engineer, video_editor, marketer |
| 🔎 **Capability Discovery** | ✅ REAL | Clona repositórios GitHub, inspeciona (linguagem, licença, scripts) e registra como capability TOOL (inventory, search_code, run_script com permissão) |
| 🖥 **Dashboard web** | ✅ REAL | Interface unificada de cartões/alertas/contexto em `http://localhost:8500` — **zero dependências** (stdlib) |
| 🧠 Memory | ✅ REAL | Mem0 (semântico) se instalado, senão SQLite 4 namespaces |
| 📅 Scheduler 24/7 | ✅ REAL | Jobs recorrentes (APScheduler): briefing de manhã, leads ao fim do dia, análise semanal |
| 📈 Self-Improvement | ✅ REAL | Avalia tarefas, regista lições, detecta gaps de capabilities |

**31 capabilities registadas** (13 reais v1.0 + 10 adapters externos + stubs legados) + **7 agentes especializados** criados automaticamente.

---

## Instalação (terminal)

```bash
# 1. Clonar
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion

# 2. Instalar dependências (só 1: httpx)
pip install -r requirements.txt

# 3. Testar (sem nenhuma API key!)
python tests/test_v1.py

# 4. Demo completo (gera briefing, edita vídeo, analisa dados, faz prospecção, escreve email)
python examples/demo_v1_completo.py

# 5. Abrir o Dashboard
python -m friday_core.dashboard --workdir friday_workspace
# → http://127.0.0.1:8500
```

Requisitos: **Python 3.10+** e (para o editor de vídeo) **ffmpeg**:
```bash
sudo apt install ffmpeg      # Linux/WSL
brew install ffmpeg          # macOS
```

Chaves de API são **opcionais** — sem elas o FRIDAY usa o planner de regras e as fontes públicas (DuckDuckGo, Google News RSS, wttr.in). Com `GEMINI_API_KEY` ganha raciocínio LLM no parse e no routing.

---

## Arquitectura v1.0

```
                  ┌─────────────────────────────┐
   Utilizador ──► │      FRIDAY (Orchestrator)  │──► Dashboard (cartões/alertas)
                  └──────────┬──────────────────┘
                             │
        ┌────────────────────┼──────────────────────┐
        ▼                    ▼                      ▼
  ObjectiveParser       Universal Router      ⚡ FastExecutor (JEV)
  (LLM ou regras)       (LLM ou regras)       ondas paralelas + cache
        │                    │                      │
        └────────────────────┼──────────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Capability Registry │ 31 capabilities
                  └──────────┬──────────┘
     ┌────────┬────────┬─────┼─────┬────────┬─────────┐
     ▼        ▼        ▼     ▼     ▼        ▼         ▼
  web_search video   data  prospect briefing email  browser/coding/
  (DDG/GPT-R) editor analyze (CRM)  (clima+ (SMTP/    agentes (7)
                           Agent-Reach notícias) draft)
                             │
        ┌────────────────────┼──────────────┐
        ▼                    ▼              ▼
  🛡 Permission System   🔄 Recovery    📈 Self-Improvement
  (READ→CRITICAL+audit)  Engine         + Memory + State
```

### Exemplo — como o FRIDAY executa uma missão de vídeo

```
TU:    "corta o video.mp4 em 8 segundos e cria versão vertical para TikTok"
FRIDAY: intent=video_edit
        plano: storyboard ∥ vertical (onda 1, PARALELO) → corte (onda 2)
        permissions: video_editor = prepare ✓
        ffmpeg: storyboard_video.jpg + cut_0_8_video.mp4 + vertical_video.mp4
        verify: ficheiros existem e têm conteúdo ✓
        → 3 artefactos prontos em outputs/video/
```

---

## Usar programaticamente

```python
from friday_core import Friday

friday = Friday(work_dir="friday_workspace")

# Missão completa (briefing, vídeo, dados, prospecção, email...)
task = friday.run("prepara o briefing de hoje")
task = friday.run("corta o video.mp4 em 15s e cria versão vertical para TikTok")
task = friday.run("encontra empresas angolanas que precisem de automação e organiza no CRM")

# Briefing proactivo + alertas
print(friday.daily_briefing(city="Luanda"))
print(friday.alerts())

# Agentes especializados
friday.create_agent("prospector")

# GitHub como fonte de capacidades
friday.discover_repo("https://github.com/browser-use/browser-use")

# Estado e retoma
print(friday.status(task.id))
friday.resume(task.id)

# Dashboard
friday.serve(port=8500)
```

### Autonomia 24/7 (scheduler)

```python
friday.scheduler.setup_default_schedule()
# 08:00 — briefing diário · 17:00 — verificação de leads · domingo — análise semanal
```

---

## Segurança e permissões (visão §29)

| Nível | Significado | Exemplo |
|---|---|---|
| `read` | ler/pesquisar informação pública | briefing, clima, notícias |
| `analyze` | processar dados localmente | data_analyze, prospecção |
| `prepare` | criar artefactos locais | documentos, edição de vídeo, rascunhos |
| `execute` | executar acções reais | automações, scripts de repos descobertos |
| `critical` | contactar pessoas / comprometer a JIAC | **enviar email de verdade** |

- Toda decisão fica em `workspace/permissions_audit.jsonl`.
- Acções CRITICAL exigem aprovação humana (callback ou botão **Aprovar/Negar no Dashboard**).
- Sem aprovação → o step falha honestamente; o email é guardado como rascunho `.eml` (nunca finge que enviou).

---

## Engines externos suportados (opcionais)

| Engine | Source | Como activar |
|--------|--------|--------------|
| browser-use | github.com/browser-use/browser-use | `pip install -e engines/browser-use` + LLM + Playwright |
| owl | github.com/camel-ai/owl | `pip install -e engines/owl` + LLM |
| openhands / SWE-agent | github.com/SWE-agent/SWE-agent | `pip install sweagent` |
| google-adk | github.com/google/adk-python | `pip install -e engines/google-adk` + GEMINI_API_KEY |
| autogen | github.com/microsoft/autogen | `pip install -e engines/autogen` + LLM |
| crewai | github.com/crewAIInc/crewAI | `pip install -e engines/crewai` + LLM |
| langgraph | github.com/langchain-ai/langgraph | `pip install -e engines/langgraph` + LLM |
| smolagents | github.com/huggingface/smolagents | `pip install -e engines/smolagents` + LLM |
| camel | github.com/camel-ai/camel | `pip install -e engines/camel` + LLM |
| gpt-researcher | github.com/assafelovic/gpt-researcher | `pip install gpt-researcher` |
| mem0 | github.com/mem0ai/mem0 | `pip install mem0ai` |
| apscheduler | — | `pip install apscheduler` (24/7) |

Todos **opcionais**: o FRIDAY detecta o que está instalado e degrada com graciosidade.

---

## Estado dos testes (sem API keys)

```
32/32 testes de fumo passaram:
  parser (7) · router (2) · permissions (4) · recovery (4) · JEV (2)
  FRIDAY e2e dados (4) · agentes (2) · video ffmpeg (1) · email honesto (3)
  proactivity (1) · dashboard (2)
5/5 missões do demo completo:
  ✓ briefing 8.2s · ✓ vídeo 10.4s · ✓ dados 0.0s · ✓ prospecção 13.3s · ✓ email 0.0s
JEV: 1ª execução 5.0s (2 ondas paralelas) · 2ª execução 0.0s (cache)
```

---

## Licenças

- **friday-fusion código próprio**: MIT (JIAC AGENCY)
- engines externos: MIT / Apache-2.0 (ver `engines/`)
- nanoMuse: GPL-3.0 ⚠️ (stub apenas — não misturar em versão proprietária)

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
