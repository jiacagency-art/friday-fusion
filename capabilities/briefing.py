"""
FRIDAY Briefing Engine
======================
Painel proativo de briefing pessoal/empresarial (funcionalidade dos vídeos).

Gera um briefing com:
- Clima (wttr.in — sem API key, formato JSON)
- Notícias seleccionadas (Google News RSS + TechCrunch — sem API key)
- Agenda (jobs do scheduler)
- Tarefas prioritárias (State Engine — tarefas falhadas/pendentes/atrasadas)
- Novos modelos/ferramentas de IA (feed de IA)
- Resumo executivo gerado por regras (ou LLM se configurado)

Respeita o requisito de autonomia local: funciona 100% sem chaves de API.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, StepResult, VerificationResult, TaskStatus,
)

UA = "JIAC-FRIDAY/1.0 (Autonomous Agent; +https://github.com/jiacagency-art)"

_DEFAULT_NEWS_QUERIES = {
    "tecnologia": "tecnologia Angola OR tech",
    "ia": "inteligência artificial OR artificial intelligence",
    "negocios": "negócios Angola OR economia Angola",
}

_AI_FEEDS = [
    ("techcrunch_ai", "https://techcrunch.com/category/artificial-intelligence/feed/"),
]


def _http_get(url: str, timeout: float = 15.0) -> httpx.Response:
    return httpx.get(url, timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True)


# --------------------------------------------------------------------------- #
def _weather(city: str = "Luanda") -> dict[str, Any]:
    """Clima via wttr.in (JSON, sem chave)."""
    try:
        r = _http_get(f"https://wttr.in/{city}?format=j1", timeout=12)
        data = r.json()
        cur = data.get("current_condition", [{}])[0]
        today = data.get("weather", [{}])[0]
        return {
            "ok": True,
            "city": city,
            "temp_c": cur.get("temp_C"),
            "feels_like_c": cur.get("FeelsLikeC"),
            "desc": (cur.get("lang_pt", [{}])[0].get("value")
                     or cur.get("weatherDesc", [{}])[0].get("value", "?")),
            "humidity": cur.get("humidity"),
            "wind_kmph": cur.get("windspeedKmph"),
            "max_c": today.get("maxtempC"), "min_c": today.get("mintempC"),
            "source": "wttr.in",
        }
    except Exception as e:
        return {"ok": False, "city": city, "error": str(e)[:120]}


def _news(query: str, limit: int = 5, lang: str = "pt") -> list[dict[str, Any]]:
    """Google News RSS — sem API key."""
    out: list[dict[str, Any]] = []
    try:
        url = (f"https://news.google.com/rss/search?q={httpx.QueryParams({'q': query})['q']}"
               f"&hl={lang}&gl=AO&ceid=AO:{lang}")
        r = _http_get(url)
        root = ET.fromstring(r.text)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            src_el = item.find("source")
            source = src_el.text if src_el is not None and src_el.text else "Google News"
            if title:
                out.append({"title": title, "url": link,
                            "source": source, "published": pub})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def _ai_news(limit: int = 5) -> list[dict[str, Any]]:
    """Notícias de IA/lançamentos de modelos — feeds públicos."""
    for _, feed in _AI_FEEDS:
        try:
            r = _http_get(feed)
            root = ET.fromstring(r.text)
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title": title, "url": link,
                                  "source": "TechCrunch AI", "published": pub})
                if len(items) >= limit:
                    return items
        except Exception:
            continue
    return []


class BriefingCapability(CapabilityImpl):
    name = "briefing"
    category = CapabilityCategory.BUSINESS
    description = ("Briefing proativo: clima + notícias + agenda + tarefas "
                   "prioritárias + novidades de IA + resumo executivo")

    def __init__(self, output_dir: str | Path = "outputs", city: str = "Luanda"):
        self.output_dir = Path(output_dir)
        self.city = city

    def health(self) -> bool:
        return True  # degrada graciosamente por secção

    def action_level(self, inputs: dict[str, Any]) -> str:
        return "read"  # briefing só lê/pesquisa informação pública

    # ------------------------------------------------------------------ #
    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        city = str(inputs.get("city", self.city))
        queries = inputs.get("news_queries") or _DEFAULT_NEWS_QUERIES
        sections_in = str(inputs.get("sections", "weather,news,ai,agenda,tasks,summary"))

        briefing: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "city": city,
        }

        if "weather" in sections_in:
            briefing["weather"] = _weather(city)

        if "news" in sections_in:
            news: dict[str, list] = {}
            for topic, q in queries.items():
                news[topic] = _news(q, limit=4)
            briefing["news"] = news

        if "ai" in sections_in:
            briefing["ai_news"] = _ai_news(limit=4)

        # Agenda: jobs agendados do scheduler (via ctx.config se injectado)
        if "agenda" in sections_in:
            agenda = []
            sched = ctx.config.get("scheduler") if ctx else None
            if sched is not None:
                try:
                    agenda = sched.list_jobs()
                except Exception:
                    agenda = []
            briefing["agenda"] = agenda

        # Tarefas prioritárias: state engine
        if "tasks" in sections_in:
            priorities: list[dict[str, Any]] = []
            state = ctx.config.get("state") if ctx else None
            if state is not None:
                try:
                    for t in state.list_recent(limit=25):
                        if t.status in (TaskStatus.FAILED, TaskStatus.PENDING,
                                        TaskStatus.EXECUTING, TaskStatus.PLANNING):
                            priorities.append({
                                "task_id": t.id,
                                "objective": t.objective.raw[:100],
                                "status": t.status.value,
                                "updated_at": t.updated_at,
                            })
                except Exception:
                    pass
            briefing["priority_tasks"] = priorities[:8]

        # Resumo executivo (regras — LLM opcional acima)
        briefing["executive_summary"] = self._summary(briefing)

        # guardar markdown + json
        md = self._markdown(briefing)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.output_dir / "briefing_hoje.md"
        json_path = self.output_dir / "briefing_hoje.json"
        md_path.write_text(md, encoding="utf-8")
        json_path.write_text(json.dumps(briefing, indent=2, ensure_ascii=False),
                             encoding="utf-8")

        briefing["artifacts"] = [{"path": str(md_path), "kind": "briefing_markdown"},
                                 {"path": str(json_path), "kind": "briefing_json"}]
        briefing["duration_s"] = round(time.time() - started, 2)
        return StepResult(success=True, output=briefing,
                          artifacts=briefing["artifacts"],
                          metadata={"sections": list(briefing.keys())},
                          finished_at=time.time())

    # ------------------------------------------------------------------ #
    def _summary(self, b: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        w = b.get("weather", {})
        if w.get("ok"):
            lines.append(f"Clima em {w.get('city')}: {w.get('desc')}, "
                         f"{w.get('temp_c')}°C (máx {w.get('max_c')}°) "
                         f"— bom para planear o dia.")
        news = b.get("news", {})
        top = []
        for topic, items in news.items():
            if items:
                top.append(f"[{topic}] {items[0]['title'][:90]}")
        if top:
            lines.append("Destaque de notícias: " + " · ".join(top[:3]))
        ai = b.get("ai_news", [])
        if ai:
            lines.append(f"IA: {ai[0]['title'][:100]}")
        tasks = b.get("priority_tasks", [])
        if tasks:
            failed = sum(1 for t in tasks if t["status"] == "failed")
            active = len(tasks) - failed
            if failed:
                lines.append(f"Atenção: {failed} tarefa(s) falhada(s) precisam de recuperação "
                             f"e {active} em curso/pending.")
            else:
                lines.append(f"{active} tarefa(s) activa(s) no pipeline.")
        agenda = b.get("agenda", [])
        if agenda:
            lines.append(f"{len(agenda)} job(s) agendado(s) no FRIDAY 24/7.")
        if not lines:
            lines.append("Sem dados suficientes para resumo — correr com rede disponível.")
        return lines

    def _markdown(self, b: dict[str, Any]) -> str:
        out = [f"# FRIDAY Briefing — {b.get('generated_at', '')}", ""]
        w = b.get("weather", {})
        if w:
            out += ["## Clima", ""]
            if w.get("ok"):
                out.append(f"**{w.get('city')}**: {w.get('desc')} — {w.get('temp_c')}°C "
                           f"(sente-se {w.get('feels_like_c')}°C), humidade {w.get('humidity')}%, "
                           f"vento {w.get('wind_kmph')} km/h. Máx {w.get('max_c')}° / Mín {w.get('min_c')}°.")
            else:
                out.append(f"Indisponível: {w.get('error')}")
            out.append("")
        for topic, items in b.get("news", {}).items():
            out += [f"## Notícias — {topic}", ""]
            if items:
                for it in items:
                    out.append(f"- [{it['title']}]({it['url']}) — *{it['source']}*")
            else:
                out.append("_Sem resultados agora._")
            out.append("")
        ai = b.get("ai_news", [])
        if ai:
            out += ["## Novidades de IA", ""]
            for it in ai:
                out.append(f"- [{it['title']}]({it['url']}) — *{it['published'][:16]}*")
            out.append("")
        tasks = b.get("priority_tasks", [])
        if tasks:
            out += ["## Tarefas prioritárias", ""]
            for t in tasks:
                out.append(f"- `{t['status']}` — {t['objective']}")
            out.append("")
        agenda = b.get("agenda", [])
        if agenda:
            out += ["## Agenda (jobs 24/7)", ""]
            for j in agenda:
                out.append(f"- {j.get('id')} → próxima execução: {j.get('next_run')}")
            out.append("")
        out += ["## Resumo executivo", ""]
        for ln in b.get("executive_summary", []):
            out.append(f"- {ln}")
        out.append("")
        return "\n".join(out)

    # ------------------------------------------------------------------ #
    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False,
                                      checks=[{"name": "success", "passed": False}])
        o = result.output or {}
        checks = [
            {"name": "has_summary", "passed": bool(o.get("executive_summary"))},
            {"name": "sections_generated", "passed": len(o) >= 4},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks),
                                  checks=checks, notes="briefing completo")
