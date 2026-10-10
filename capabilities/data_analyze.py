"""
FRIDAY Data Engine
==================
Análise e processamento de dados (visão §16) — só com stdlib:
- Leitura de CSV/JSON
- Perfil por coluna (tipo, ausentes, cardinalidade)
- Estatísticas numéricas (média, mediana, desvio, min/max, quartis)
- Top valores categóricos
- Correlações numéricas (Pearson, calculado à mão)
- Agrupamento (group_by → agregações sum/mean/count)
- Exporta relatório Markdown + JSON no workspace
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, StepResult, VerificationResult,
)


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    x, y = xs[:n], ys[:n]
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return 0.0
    return round(num / (dx * dy), 4)


class DataAnalyzeCapability(CapabilityImpl):
    name = "data_analyze"
    category = CapabilityCategory.DATA
    description = "Data Engine — analisa CSV/JSON: perfil, estatísticas, correlações, group-by, relatório"

    def __init__(self, output_dir: str | Path = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def health(self) -> bool:
        return True

    def action_level(self, inputs: dict[str, Any]) -> str:
        return "analyze"  # análise local de dados

    # ------------------------------------------------------------------ #
    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        path = Path(inputs.get("path", ""))
        if not path.exists():
            for base in (Path.cwd(), self.output_dir,
                         self.output_dir.parent, self.output_dir.parent.parent):
                cand = base / path
                if cand.exists():
                    path = cand
                    break
            else:
                return StepResult(success=False,
                                  error=f"ficheiro não encontrado: {inputs.get('path')}",
                                  finished_at=time.time())

        suffix = path.suffix.lower()
        if suffix == ".json":
            rows = self._load_json(path)
        elif suffix in (".csv", ".txt", ".tsv"):
            rows = self._load_csv(path)
        else:
            return StepResult(success=False,
                              error=f"formato não suportado: {suffix} (csv/json)",
                              finished_at=time.time())

        if not rows:
            return StepResult(success=False, error="dataset vazio",
                              finished_at=time.time())

        analysis = self._profile(rows)
        group_col = inputs.get("group_by")
        if group_col:
            agg = str(inputs.get("agg", "count"))
            analysis["group_by"] = self._groupby(rows, str(group_col), agg)

        analysis["file"] = str(path)
        analysis["analyzed_at"] = datetime.now().isoformat(timespec="seconds")
        analysis["duration_s"] = round(time.time() - started, 2)

        md = self._markdown(analysis)
        md_path = self.output_dir / f"analise_{path.stem}.md"
        json_path = self.output_dir / f"analise_{path.stem}.json"
        md_path.write_text(md, encoding="utf-8")
        json_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False),
                             encoding="utf-8")

        analysis["artifacts"] = [{"path": str(md_path), "kind": "analysis_markdown"},
                                 {"path": str(json_path), "kind": "analysis_json"}]
        return StepResult(success=True, output=analysis,
                          artifacts=analysis["artifacts"],
                          metadata={"rows": analysis["rows"],
                                    "columns": analysis["columns_count"]},
                          finished_at=time.time())

    # ------------------------------------------------------------------ #
    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False,
                                      checks=[{"name": "success", "passed": False}])
        o = result.output or {}
        checks = [{"name": "has_rows", "passed": o.get("rows", 0) > 0},
                  {"name": "has_profile", "passed": bool(o.get("profile"))}]
        return VerificationResult(passed=all(c["passed"] for c in checks),
                                  checks=checks, notes="análise validada")

    # ================================================================== #
    def _load_csv(self, path: Path) -> list[dict[str, str]]:
        delim = ";" if path.suffix.lower() == ".tsv" else None
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                class D(csv.excel):
                    delimiter = delim or ","
                dialect = D
            return [dict(r) for r in csv.DictReader(f, dialect=dialect)]

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v
        return []

    # ------------------------------------------------------------------ #
    def _profile(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        columns: dict[str, dict[str, Any]] = {}
        n = len(rows)
        names = sorted({k for r in rows for k in r.keys()})
        for col in names:
            values = [r.get(col) for r in rows]
            str_vals = ["" if v is None else str(v).strip() for v in values]
            missing = sum(1 for v in str_vals if v == "")
            non_empty = [v for v in str_vals if v != ""]
            numeric = [float(v) for v in non_empty if _is_number(v)]
            unique = len(set(non_empty))
            kind = ("numeric" if numeric and len(numeric) >= 0.7 * len(non_empty)
                    else "categorical" if unique <= max(30, 0.5 * n) else "text")
            entry: dict[str, Any] = {
                "missing": missing,
                "unique": unique,
                "kind": kind,
            }
            if kind == "numeric" and numeric:
                entry.update({
                    "mean": round(statistics.fmean(numeric), 4),
                    "median": round(statistics.median(numeric), 4),
                    "stdev": round(statistics.stdev(numeric), 4) if len(numeric) > 1 else 0.0,
                    "min": min(numeric), "max": max(numeric),
                })
            elif kind == "categorical":
                counts: dict[str, int] = {}
                for v in non_empty:
                    counts[v] = counts.get(v, 0) + 1
                entry["top_values"] = sorted(counts.items(),
                                             key=lambda kv: -kv[1])[:10]
            columns[col] = entry

        # correlações numéricas
        numeric_cols = [c for c, e in columns.items() if e.get("kind") == "numeric"]
        correlations = []
        for i, a in enumerate(numeric_cols):
            for b in numeric_cols[i + 1:]:
                xs = [float(r[a]) for r in rows
                      if r.get(a) not in (None, "") and _is_number(str(r.get(a)))]
                ys = [float(r[b]) for r in rows
                      if r.get(b) not in (None, "") and _is_number(str(r.get(b)))]
                r_val = _pearson(xs, ys)
                if abs(r_val) >= 0.5:
                    correlations.append({"a": a, "b": b, "pearson": r_val})

        return {
            "rows": n, "columns_count": len(names),
            "profile": columns, "correlations": correlations[:12],
        }

    def _groupby(self, rows: list[dict[str, Any]],
                 col: str, agg: str) -> list[dict[str, Any]]:
        groups: dict[str, list] = {}
        for r in rows:
            groups.setdefault(str(r.get(col, "")), []).append(r)
        out = []
        for key, rs in groups.items():
            entry = {"value": key, "count": len(rs)}
            if agg in ("sum", "mean") and rs:
                numeric_col = next(
                    (c for c in rs[0]
                     if c != col and all(_is_number(str(r.get(c, ""))) for r in rs)),
                    None)
                if numeric_col:
                    vals = [float(r[numeric_col]) for r in rs]
                    entry["column"] = numeric_col
                    entry["sum"] = round(sum(vals), 4)
                    entry["mean"] = round(statistics.fmean(vals), 4)
            out.append(entry)
        return sorted(out, key=lambda e: -e["count"])[:20]

    # ------------------------------------------------------------------ #
    def _markdown(self, a: dict[str, Any]) -> str:
        out = [f"# Análise de Dados — {a.get('file', '')}", "",
               f"- Linhas: **{a['rows']}** · Colunas: **{a['columns_count']}**",
               f"- Gerado: {a.get('analyzed_at')}", "", "## Perfil por coluna", ""]
        for col, e in a.get("profile", {}).items():
            kind = e.get("kind", "?")
            line = f"- **{col}** ({kind}) — únicos: {e.get('unique')}, ausentes: {e.get('missing')}"
            if kind == "numeric":
                line += (f", média: {e.get('mean')}, mediana: {e.get('median')}, "
                         f"min: {e.get('min')}, max: {e.get('max')}")
            elif kind == "categorical" and e.get("top_values"):
                tops = ", ".join(f"{k} ({v})" for k, v in e["top_values"][:5])
                line += f" — top: {tops}"
            out.append(line)
        if a.get("correlations"):
            out += ["", "## Correlações fortes (|r| ≥ 0.5)", ""]
            for c in a["correlations"]:
                out.append(f"- {c['a']} ↔ {c['b']}: r = {c['pearson']}")
        if a.get("group_by"):
            out += ["", "## Agrupamento", ""]
            for g in a["group_by"]:
                extra = (f" · {g.get('column')}: soma={g.get('sum')}, média={g.get('mean')}"
                         if g.get("column") else "")
                out.append(f"- {g['value']}: {g['count']} linha(s){extra}")
        out.append("")
        return "\n".join(out)
