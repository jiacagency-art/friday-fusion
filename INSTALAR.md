# INSTALAR O JIAC FRIDAY — Guia simples de terminal

> Tempo total: ~3 minutos. Sem nenhuma API key obrigatória.

---

## 1. Requisitos

- **Python 3.10 ou superior** (`python3 --version`)
- **Git** (`git --version`)
- **ffmpeg** — só para o editor de vídeo (opcional)

Instalar o que falta:

```bash
# Ubuntu / Linux / WSL
sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg

# macOS (com Homebrew)
brew install python git ffmpeg

# Windows (PowerShell, como administrador)
winget install Python.Python.3.12 Git.Git Gyan.FFmpeg
```

---

## 2. Baixar e instalar o FRIDAY

```bash
git clone https://github.com/jiacagency-art/friday-fusion.git
cd friday-fusion
pip install -r requirements.txt
```

> Se o `pip` reclamar de permissões, usa: `pip install --user -r requirements.txt`

---

## 3. Testar que tudo funciona

```bash
# Testes de fumo (32 testes — não precisa de nenhuma API key)
python tests/test_v1.py

# Demo completo: briefing + edição de vídeo + análise de dados
# + prospecção CRM + email de rascunho
python examples/demo_v1_completo.py
```

No fim, o demo mostra os artefactos gerados em `demo_workspace_v1/outputs/`.

---

## 4. Abrir o Dashboard (cartões, alertas, missões)

```bash
python -m friday_core.dashboard --workdir friday_workspace
```

Abre o browser em: **http://127.0.0.1:8500**

No dashboard podes:
- Dar missões em linguagem natural (caixa no topo)
- Ver o **briefing proativo** (clima, notícias, IA, tarefas)
- Ver **alertas** do FRIDAY e **aprovar/negar** acções críticas
- Ver as missões, capabilities e métricas JEV em tempo real

---

## 5. Configurações opcionais (só se quiseres mais poder)

```bash
cp .env.example .env
nano .env        # ou vim / code .env
```

| Chave | Para que serve | Onde obter |
|---|---|---|
| `GEMINI_API_KEY` | Raciocínio LLM no parse e routing | https://aistudio.google.com/apikey |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | Enviar email de verdade (senão fica rascunho) | O teu provedor de email |
| `FRIDAY_WORKSPACE` | Pasta de trabalho do FRIDAY | — |

Sem nenhuma chave: o FRIDAY funciona com fontes públicas (DuckDuckGo, Google News RSS, wttr.in) e o planner de regras.

---

## 6. Usar no dia-a-dia

```bash
# Dashboard (uso normal)
python -m friday_core.dashboard --workdir friday_workspace

# Missão rápida por terminal (sem dashboard)
python -c "
from friday_core import Friday
f = Friday(work_dir='friday_workspace')
t = f.run('prepara o briefing de hoje')
print(t.status.value)
"

# Autonomia 24/7 (briefing 08:00, leads 17:00, análise semanal)
python -c "
from friday_core import Friday
f = Friday(work_dir='friday_workspace')
f.scheduler.setup_default_schedule()
import time
while True: time.sleep(60)
"
```

### Exemplos de missões que já funcionam

- `prepara o briefing de hoje` — clima + notícias + IA + resumo
- `corta o video.mp4 em 15 segundos e cria versão vertical para TikTok`
- `analisa o dados.csv com estatísticas`
- `encontra empresas angolanas que precisem de automação e organiza no CRM`
- `escreve email para geral@jiac.ao com o relatório` (rascunho; com SMTP configurado pede aprovação no dashboard)

---

## Problemas comuns

| Problema | Solução |
|---|---|
| `ModuleNotFoundError: httpx` | `pip install httpx` |
| `ffmpeg não instalado` | `sudo apt install ffmpeg` (Linux) / `brew install ffmpeg` (macOS) |
| Porta 8500 ocupada | `python -m friday_core.dashboard --port 8600` |
| Notícias não carregam | Verifica a internet; as fontes são públicas (Google News RSS) |
| Quero apagar tudo e recomeçar | apaga a pasta `friday_workspace/` |

---

**JIAC AGENCY** — Tu dás o objetivo. O FRIDAY transforma o objetivo em trabalho.
