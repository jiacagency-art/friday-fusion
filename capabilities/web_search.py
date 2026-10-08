"""Web Search Capability — DuckDuckGo HTML (sem API key)."""

from __future__ import annotations
import re
import time
import urllib.parse
from typing import Any
import httpx
from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


_DDG_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class WebSearchCapability(CapabilityImpl):
    name = "web_search"
    category = CapabilityCategory.RESEARCH
    description = "Pesquisa web via DuckDuckGo (sem API key)"

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        query = inputs.get("query") or inputs.get("q")
        if not query:
            return StepResult(success=False, error="query é obrigatório")
        max_results = int(inputs.get("max_results", 10))
        started = time.time()
        ctx.logger(f"[web_search] query={query!r} max={max_results}")
        try:
            results = self._search(query, max_results)
            return StepResult(
                success=True, output=results,
                metadata={"engine": "duckduckgo_html", "query": query,
                          "result_count": len(results),
                          "duration_s": round(time.time() - started, 2)},
                finished_at=time.time(),
            )
        except Exception as e:
            ctx.logger(f"[web_search] erro: {e}", level="error")
            return StepResult(success=False, error=str(e), finished_at=time.time())

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        checks = []
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        results = result.output or []
        checks.append({
            "name": "has_results", "passed": len(results) > 0, "actual": len(results),
        })
        if results:
            sample = results[0]
            required = {"title", "url"}
            checks.append({
                "name": "result_schema", "passed": required.issubset(sample.keys()),
                "missing": list(required - set(sample.keys())),
            })
        return VerificationResult(
            passed=all(c["passed"] for c in checks), checks=checks,
        )

    def health(self) -> bool:
        try:
            r = httpx.get("https://duckduckgo.com", timeout=5.0,
                          headers={"User-Agent": _USER_AGENT})
            return r.status_code in (200, 301, 302)
        except Exception:
            return False

    def _search(self, query: str, max_results: int) -> list[dict]:
        params = {"q": query, "kl": "wt-wt"}
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "pt-PT,en;q=0.5"}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(_DDG_URL, params=params, headers=headers)
            r.raise_for_status()
            html = r.text
        return self._parse_html(html, max_results)

    def _parse_html(self, html: str, max_results: int) -> list[dict]:
        results: list[dict] = []
        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        )
        for url_raw, title_raw, snippet_raw in blocks:
            if len(results) >= max_results:
                break
            url = self._unwrap_ddg_url(url_raw)
            title = self._strip_html(title_raw).strip()
            snippet = self._strip_html(snippet_raw).strip()
            if not title or not url:
                continue
            results.append({"title": title, "url": url, "snippet": snippet})
        return results

    @staticmethod
    def _unwrap_ddg_url(href: str) -> str:
        if "uddg=" in href:
            qs = href.split("uddg=", 1)[1].split("&", 1)[0]
            return urllib.parse.unquote(qs)
        return href

    @staticmethod
    def _strip_html(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s).replace("&amp;", "&").replace("&nbsp;", " ")
