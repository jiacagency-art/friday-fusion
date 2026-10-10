"""Objective Parser — NL → Objective via regras (swap-ready para LLM)."""

from __future__ import annotations
import re
from typing import Any
from .types import Objective


_INTENT_PATTERNS: list[tuple[str, re.Pattern, dict[str, Any]]] = [
    # v1.0 intents — ordem importa: mais específicos primeiro
    ("video_edit", re.compile(
        r"(v[íi]deo|video|clip|corta?\s+(?:o|a)?\s*v[íi]deo|legend[ae][a-z]*|"
        r"tiktok|reels?|storyboard|vertical|gif|destaca?\b.*v[íi]deo)", re.IGNORECASE),
     {"default_capability": "video_editor"}),
    ("briefing", re.compile(
        r"(briefing|bom dia|resumo do dia|o que tenho hoje|me actualiza|"
        r"me atualiza|not[íi]cias de hoje|clima|tempo em)", re.IGNORECASE),
     {"default_capability": "briefing"}),
    ("data_analyze", re.compile(
        r"(analis[ae][a-z]*\s+(?:o\s+)?(?:csv|dados|ficheiro|excel)|estat[íi]stica|"
        r"correla|group ?by|agrupa?\b)", re.IGNORECASE),
     {"default_capability": "data_analyze"}),
    ("prospect", re.compile(
        r"(prospec[çc][ãa]o|leads?|clientes?\s+potenciais|empresas\s+que\s+podam?|"
        r"empresas\s+que\s+possam|crm|lista\s+comercial|oportunidades\s+comerciais|"
        r"encontra\s+empresas)", re.IGNORECASE),
     {"default_capability": "prospect_real"}),
    ("email", re.compile(
        r"(envi[ae][a-z]*\s+(?:um\s+)?(?:email|e-mail|mail)|escrev[ae][a-z]*\s+email|"
        r"manda?\s+(?:um\s+)?email)", re.IGNORECASE),
     {"default_capability": "email_send"}),
    ("research", re.compile(
        r"(pesquis[ae][a-z]*|investig[ae][a-z]*|estud[ae][a-z]*|"
        r"analis[ae][a-z]*|descobr[ae][a-z]*|encontr[ae][a-z]*|"
        r"identific[ae][a-z]*|procur[ae][a-z]*|find|search|research)", re.IGNORECASE),
     {"default_capability": "web_search"}),
    ("build", re.compile(
        r"(cri[ae][a-z]*|constro[ie][a-z]*|desenvolv[ae][a-z]*|"
        r"implement[ae][a-z]*|mont[ae][a-z]*|build|create|develop)", re.IGNORECASE),
     {"default_capability": "coding_openhands"}),
    ("operate", re.compile(
        r"(entr[ae][a-z]*\sno|abr[ae][a-z]*\so|acess[ae][a-z]*|"
        r"verific[ae][a-z]*\sos|actualiz[ae][a-z]*|envi[ae][a-z]*|"
        r"open|access|update|send)", re.IGNORECASE),
     {"default_capability": "browser_navigate"}),
    ("report", re.compile(r"(relat[óo]rio|report|summary|resumo|lista|list)", re.IGNORECASE),
     {"default_capability": "documents_create"}),
]

_COUNT_PATTERN = re.compile(r"\b(\d+)\b", re.IGNORECASE)
_QUOTE_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'|«([^»]+)»')
_TARGET_PATTERNS = [
    ("companies", re.compile(r"empresas|companies|businesses|negócios", re.IGNORECASE)),
    ("people", re.compile(r"pessoas|decisores|contacts?|people", re.IGNORECASE)),
    ("market", re.compile(r"mercado|market|segmento|sector", re.IGNORECASE)),
    ("site", re.compile(r"\bsite|website|página|landing", re.IGNORECASE)),
    ("app", re.compile(r"\bapp|aplicação|software|platform|plataforma|saas", re.IGNORECASE)),
    ("crm", re.compile(r"\bcrm\b", re.IGNORECASE)),
    ("clients", re.compile(r"clientes?|clients?|leads?", re.IGNORECASE)),
]


def parse(raw: str, user_id: str = "default") -> Objective:
    normalized = raw.strip().lower()
    intent = "research"
    intent_meta = {"default_capability": "web_search"}

    for candidate_intent, pattern, meta in _INTENT_PATTERNS:
        if pattern.search(normalized):
            intent = candidate_intent
            intent_meta = meta
            break

    entities: dict[str, Any] = {}

    count_match = _COUNT_PATTERN.search(normalized)
    if count_match:
        entities["count"] = int(count_match.group(1))

    quote_match = _QUOTE_PATTERN.search(raw)
    if quote_match:
        entities["quoted"] = next(g for g in quote_match.groups() if g)

    for target_name, pattern in _TARGET_PATTERNS:
        if pattern.search(normalized):
            entities.setdefault("targets", []).append(target_name)

    query = _extract_query(raw, intent)
    if query:
        entities["query"] = query

    entities["default_capability"] = intent_meta["default_capability"]

    # v1.0: texto completo disponível para planners especializados
    entities["raw"] = raw.strip()

    # v1.0: ficheiro de vídeo/dados mencionado (ex.: "video.mp4", "dados.csv")
    file_m = re.search(r"([A-Za-z0-9_\-.]+\.(?:mp4|mov|avi|mkv|webm|gif|csv|tsv|json))",
                       raw, re.IGNORECASE)
    if file_m:
        fname = file_m.group(1).strip()
        if fname.lower().endswith((".csv", ".tsv", ".json")):
            entities.setdefault("path", fname)
        else:
            entities.setdefault("source", fname)

    # v1.0: cidade para briefing/clima
    city_m = re.search(r"(?:clima|tempo|briefing)\s+(?:em|de|para)\s+([A-ZÁÂÃÉÊÍÓÔÕÚÇ][\wáâãéêíóôõúç]+)",
                       raw, re.IGNORECASE)
    if city_m:
        entities["city"] = city_m.group(1).title()

    # v1.0: destinatário de email
    email_m = re.search(r"([\w.+-]+@[\w-]+\.[\w.-]+)", raw)
    if email_m:
        entities["to"] = email_m.group(1)

    return Objective(
        raw=raw, normalized=normalized, intent=intent,
        entities=entities, user_id=user_id,
    )


def _extract_query(raw: str, intent: str) -> str | None:
    text = raw.strip()
    verbs = {
        "research": ["pesquisa", "pesquise", "pesquisar", "procura", "procure",
                     "encontra", "encontre", "encontrar", "descobre", "descobrir",
                     "find", "search"],
        "build": ["cria", "crie", "criar", "constroi", "construir", "desenvolve",
                  "faz", "faça", "build", "create"],
        "operate": ["entra", "entre", "abre", "abra", "verifica", "verifique"],
        "report": ["prepara", "prepare", "gera", "gere", "produz"],
    }
    for v in verbs.get(intent, []):
        if text.lower().startswith(v + " "):
            return text[len(v):].strip(" .,;:!")
    return text
