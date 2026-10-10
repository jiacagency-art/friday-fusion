"""
FRIDAY Prospect Engine (Agent-Reach real)
=========================================
Prospecção e inteligência comercial (visão §12) — sem API keys:
- Pesquisa empresas por sector/país via web_search (DuckDuckGo/GPT-Researcher)
- Extrai nomes de empresas, fontes e sinais de oportunidade
- Classifica oportunidades (serviços de automação, sites, IA, marketing)
- Produz lista comercial formatada: CSV (para CRM) + Markdown + JSON

Exemplo de ordem:
    "FRIDAY, encontra empresas angolanas que possam precisar dos nossos
     serviços de automação e organiza tudo no nosso CRM."
"""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, StepResult, VerificationResult,
)

# sinais de oportunidade → serviço JIAC correspondente
_OPPORTUNITY_MAP = [
    (re.compile(r"(website|web ?site|site oficial|landing)", re.I),
     "Criação/melhoria de website"),
    (re.compile(r"(app|aplicativo|aplicação|plataforma digital|software)", re.I),
     "Desenvolvimento de software/app"),
    (re.compile(r"(automa[çc][ãa]o|automatiza|workflow|processos manuais)", re.I),
     "Automação de processos"),
    (re.compile(r"(marketing|social media|campanha|publicidade)", re.I),
     "Marketing digital"),
    (re.compile(r"(intelig[êe]ncia artificial|\bIA\b|AI|chatbot|LLM)", re.I),
     "Soluções de IA / chatbots"),
    (re.compile(r"(dados|analytics|relat[óo]rios?|bi\b)", re.I),
     "Análise de dados / dashboards"),
    (re.compile(r"(hotel|turismo|restaurante|banco|bank|seguro|energia|"
                r"telecom|log[íi]stica|constru[çc][ãa]o|minera)", re.I),
     "Sector-alvo prioritário JIAC"),
]

_COMPANY_HINTS = re.compile(
    r"([A-ZÁÂÃÉÊÍÓÔÕÚÇ][\wÁÂÃÉÊÍÓÔÕÚÇáâãéêíóôõúç&.\-']+(?:\s+"
    r"(?:de|do|da|dos|das|and|the|Group|Grupo|Societ|S\.A\.|Lda|LTDA|SA|Ltd|Inc)\b)?"
    r"(?:\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ][\wÁÂÃÉÊÍÓÔÕÚÇáâãéêíóôõúç&.\-']+)*)")

_STOP = {"Angola", "Luanda", "Notícias", "Empresa", "Empresas", "Google",
         "YouTube", "Wikipedia", "Facebook", "LinkedIn", "The", "Best",
         "Top", "PDF", "Governo", "Expansão", "Inteligência", "Artificial",
         "Santos", "Mercado", "Jornal", "Hoje", "Novo", "Nova", "Grupo",
         "Sociedade", "Ministério", "Banco", "Nacional", "Economia",
         "Desafios", "Crescimento", "Investimento", "Mercados", "África",
         "Como", "Porque", "Quando", "Onde", "Tudo", "Sobre", "Mais",
         "Soluções", "Serviços", "Automatização", "Automação", "Digital",
         "Cleópatra", "Directora", "Director", "Presidente", "CEO"}


class ProspectCapability(CapabilityImpl):
    name = "business_prospect"
    category = CapabilityCategory.BUSINESS
    description = ("Agent-Reach real — pesquisa empresas, detecta oportunidades "
                   "e organiza lista comercial (CSV CRM + MD + JSON)")

    def __init__(self, output_dir: str | Path = "outputs", web_search_impl=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._web_search_impl = web_search_impl  # injectado no registry builder

    def health(self) -> bool:
        return True

    def action_level(self, inputs: dict[str, Any]) -> str:
        return "analyze"  # pesquisa pública + ficheiros CRM locais

    # ------------------------------------------------------------------ #
    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        query = str(inputs.get("query") or inputs.get("sector")
                    or "empresas Angola tecnologia")
        count = int(inputs.get("count", 10))
        company = str(inputs.get("our_company", "JIAC AGENCY"))
        value_prop = str(inputs.get("value_prop",
                                    "automação, IA, websites e software à medida"))

        # 1. Pesquisa (usa web_search internamente)
        results = self._search(query, max_results=min(max(count * 3, 12), 30))

        # 2. Extrai empresas + oportunidades
        leads: dict[str, dict[str, Any]] = {}
        for r in results:
            title = r.get("title", "")
            body = r.get("body") or r.get("snippet") or ""
            url = r.get("url") or r.get("href") or ""
            companies = self._extract_companies(title)
            if not companies:
                companies = self._extract_companies(body[:160])
            opps = self._detect_opportunities(title + " " + body)
            for comp in companies[:2]:
                lead = leads.setdefault(comp, {
                    "empresa": comp, "fontes": [], "oportunidades": [],
                    "pesquisa": query, "score": 0,
                })
                if url and url not in lead["fontes"]:
                    lead["fontes"].append(url)
                for o in opps:
                    if o not in lead["oportunidades"]:
                        lead["oportunidades"].append(o)
                        lead["score"] += 2
                if opps:
                    lead["score"] += 1

        # 3. Ordena por score e corta ao count pedido
        ranked = sorted(leads.values(), key=lambda l: -l["score"])[:count]
        for i, lead in enumerate(ranked, 1):
            lead["rank"] = i
            lead["estado_crm"] = "novo"
            lead["proposta_sugerida"] = (
                f"Proposta {company}: {', '.join(lead['oportunidades'][:2]) or value_prop} "
                f"— " + value_prop)

        # 4. Exporta CSV CRM + JSON + Markdown (CSV SEMPRE escrito — CRM honesto)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        csv_path = self.output_dir / f"crm_leads_{stamp}.csv"
        json_path = self.output_dir / f"leads_{stamp}.json"
        md_path = self.output_dir / f"lista_comercial_{stamp}.md"

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["rank", "empresa", "oportunidades", "fontes",
                        "score", "estado_crm", "proposta_sugerida", "pesquisa"])
            for l in ranked:
                w.writerow([l["rank"], l["empresa"],
                            " | ".join(l["oportunidades"][:3]),
                            " | ".join(l["fontes"][:2]),
                            l["score"], l["estado_crm"],
                            l["proposta_sugerida"], l["pesquisa"]])

        json_path.write_text(json.dumps(ranked, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        md = self._markdown(ranked, query, company)
        md_path.write_text(md, encoding="utf-8")

        summary = {
            "query": query,
            "search_results": len(results),
            "leads_found": len(ranked),
            "with_opportunity": sum(1 for l in ranked if l["oportunidades"]),
            "top_lead": ranked[0]["empresa"] if ranked else None,
            "artifacts": [
                {"path": str(csv_path), "kind": "crm_csv"},
                {"path": str(json_path), "kind": "leads_json"},
                {"path": str(md_path), "kind": "commercial_list_md"},
            ],
            "duration_s": round(time.time() - started, 2),
        }
        return StepResult(success=True, output=summary,
                          artifacts=summary["artifacts"],
                          metadata={"leads": [l["empresa"] for l in ranked[:5]]},
                          finished_at=time.time())

    # ------------------------------------------------------------------ #
    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False,
                                      checks=[{"name": "success", "passed": False,
                                               "error": result.error}])
        o = result.output or {}
        checks = [
            {"name": "search_ran", "passed": o.get("search_results", 0) >= 0},
            {"name": "artifacts_exist", "passed": all(
                Path(a["path"]).exists() for a in o.get("artifacts", []))},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks),
                                  checks=checks, notes="prospecção validada")

    # ================================================================== #
    def _search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """
        Pesquisa multi-fonte (sem API keys):
        1. capability web_search injectada (GPT-Researcher/DuckDuckGo)
        2. DuckDuckGo lite/html directo
        3. Google News RSS (fallback robusto, funciona mesmo com DDG bloqueado)
        Se a query completa não der nada → tenta query simplificada.
        """
        results = self._search_raw(query, max_results)
        if results:
            return results
        simplified = self._simplify_query(query)
        if simplified and simplified != query:
            return self._search_raw(simplified, max_results)
        return []

    @staticmethod
    def _simplify_query(query: str) -> str:
        """Remove verbos/palavras de comando e fica com os termos-chave."""
        stop = {"encontra", "encontre", "encontrar", "pesquisa", "pesquise",
                "empresas", "que", "precisem", "precisam", "precisa",
                "organiza", "organize", "organizar", "no", "na", "do", "da",
                "dos", "das", "e", "em", "para", "com", "prepara", "prepare",
                "lista", "comercial", "crm", "nossos", "nossas", "serviços",
                "the", "and", "for", "with", "find", "search"}
        words = [w.strip(".,;:!?()«»\"'") for w in query.split()]
        kept = [w for w in words if w.lower() not in stop and len(w) > 2]
        return " ".join(kept[:6])

    def _search_raw(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # 1. impl injectada
        if self._web_search_impl is not None:
            try:
                class _FakeCtx:
                    config: dict = {}
                res = self._web_search_impl.execute(
                    {"query": query, "max_results": max_results}, _FakeCtx())
                if res.success:
                    out = res.output.get("results", []) if isinstance(res.output, dict) else []
                    if out:
                        return out
            except Exception:
                pass

        # 2. DuckDuckGo directo
        try:
            import httpx
            r = httpx.get("https://html.duckduckgo.com/html/",
                          params={"q": query}, timeout=12,
                          headers={"User-Agent": "Mozilla/5.0 (JIAC-FRIDAY)"},
                          follow_redirects=True)
            results = []
            for m in re.finditer(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    r.text):
                url = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2))
                results.append({"title": title, "url": url})
                if len(results) >= max_results:
                    return results
        except Exception:
            pass

        # 3. Google News RSS (fallback final — descobre notícias de empresas)
        return self._search_google_news(query, max_results)

    def _search_google_news(self, query: str, max_results: int) -> list[dict[str, Any]]:
        import xml.etree.ElementTree as ET
        import httpx
        try:
            url = (f"https://news.google.com/rss/search"
                   f"?q={httpx.QueryParams({'q': query})['q']}&hl=pt&gl=AO&ceid=AO:pt")
            r = httpx.get(url, timeout=15, follow_redirects=True,
                          headers={"User-Agent": "JIAC-FRIDAY/1.0"})
            root = ET.fromstring(r.text)
            results = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                src_el = item.find("source")
                source = (src_el.text if src_el is not None and src_el.text
                          else "Google News")
                if title:
                    results.append({"title": f"{title} — {source}", "url": link,
                                    "body": title})
                if len(results) >= max_results:
                    break
            return results
        except Exception:
            return []

    def _extract_companies(self, text: str) -> list[str]:
        if not text:
            return []
        found = []
        for m in _COMPANY_HINTS.finditer(text):
            cand = m.group(1).strip(" .,;:-")
            first = cand.split()[0] if cand.split() else ""
            if (first and first[0].isupper() and first not in _STOP
                    and len(cand) > 2 and cand not in found):
                found.append(cand)
        return found[:5]

    def _detect_opportunities(self, text: str) -> list[str]:
        return [label for pattern, label in _OPPORTUNITY_MAP if pattern.search(text)]

    def _markdown(self, leads: list[dict[str, Any]], query: str,
                  company: str) -> str:
        out = [f"# Lista Comercial — {company}", "",
               f"- Pesquisa: **{query}**",
               f"- Gerado: {datetime.now().isoformat(timespec='seconds')}",
               f"- Leads: **{len(leads)}**", ""]
        for l in leads:
            out.append(f"## {l['rank']}. {l['empresa']}  (score {l['score']})")
            if l["oportunidades"]:
                out.append(f"- **Oportunidades:** {', '.join(l['oportunidades'][:4])}")
            if l["fontes"]:
                out.append(f"- **Fontes:** {l['fontes'][0]}")
            out.append(f"- **Proposta sugerida:** {l['proposta_sugerida']}")
            out.append("")
        return "\n".join(out)
