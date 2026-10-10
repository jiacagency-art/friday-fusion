"""
FRIDAY Capability Discovery
===========================
"Repositórios GitHub como fonte de capacidades" (visão — autonomia local).

O FRIDAY descobre novas ferramentas sozinho:
1. `discover(repo_url)` — clona shallow, inspeciona README/pyproject/package.json,
   identifica linguagem, licença, pontos de entrada e scripts.
2. Registra uma capability `gh_<slug>` (categoria TOOL) que sabe:
   - devolver o inventário do repo
   - localizar código relevante por keyword
   - executar scripts CLI seguros do repo (se a policy permitir EXECUTE)
3. Tudo auditado; nunca corre código automaticamente sem permission check.

Uso:
    disc = CapabilityDiscovery(registry, work_dir, permissions)
    meta = disc.discover("https://github.com/browser-use/browser-use")
    res  = friday.run("procura no repo browser_use como se faz screenshot")
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .types import Capability, CapabilityCategory, CapabilityImpl, StepResult, VerificationResult

_SAFE_CMD = re.compile(r"^[\w./:=\- ]+$")


class _GitHubRepoTool(CapabilityImpl):
    """Capability TOOL que conhece um repo GitHub clonado."""

    def __init__(self, meta: dict[str, Any], permissions=None, logger=None):
        self.name = meta["capability_name"]
        self.category = CapabilityCategory.TOOL
        self.description = f"GitHub tool: {meta['repo']} — {meta.get('description', '')[:100]}"
        self.meta = meta
        self.permissions = permissions
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))

    def health(self) -> bool:
        return Path(self.meta.get("path", "__missing__")).exists()

    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        action = str(inputs.get("action", "inventory")).lower()
        repo_path = Path(self.meta["path"])

        if action in ("inventory", "info"):
            return StepResult(success=True, output={"action": action, **self.meta},
                              metadata={"repo": self.meta["repo"]},
                              finished_at=time.time())

        if action == "search_code":
            keyword = str(inputs.get("keyword") or inputs.get("query") or "")
            if not keyword:
                return StepResult(success=False, error="keyword obrigatória",
                                  finished_at=time.time())
            hits = []
            try:
                out = subprocess.run(
                    ["grep", "-rIl", "--include=*.py", "--include=*.md",
                     "--include=*.js", "--include=*.ts", "--include=*.json",
                     "-e", keyword, str(repo_path)],
                    capture_output=True, text=True, timeout=30)
                files = [f for f in out.stdout.strip().splitlines() if f][:20]
                for fpath in files:
                    try:
                        text = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(text.splitlines(), 1):
                            if keyword.lower() in line.lower():
                                hits.append({"file": str(Path(fpath).relative_to(repo_path)),
                                             "line": i, "text": line.strip()[:160]})
                                if len(hits) >= 30:
                                    break
                        if len(hits) >= 30:
                            break
                    except Exception:
                        continue
            except Exception as e:
                return StepResult(success=False, error=str(e)[:200],
                                  finished_at=time.time())
            summary = {"action": action, "keyword": keyword,
                       "files": len(set(h["file"] for h in hits)), "hits": hits}
            return StepResult(success=True, output=summary,
                              metadata={"repo": self.meta["repo"]},
                              finished_at=time.time())

        if action == "run_script":
            script = str(inputs.get("script", ""))
            if not script or not _SAFE_CMD.match(script):
                return StepResult(success=False,
                                  error="script inválido ou não permitido",
                                  finished_at=time.time())
            if self.permissions is not None:
                decision = self.permissions.check("execute", self.name,
                                                  requester="capability_discovery")
                if not decision.allowed:
                    return StepResult(success=False,
                                      error=f"permissions: {decision.reason}",
                                      finished_at=time.time())
            script_path = repo_path / script
            if not script_path.exists():
                return StepResult(success=False,
                                  error=f"script não existe: {script}",
                                  finished_at=time.time())
            try:
                out = subprocess.run(["bash", str(script_path)], cwd=str(repo_path),
                                     capture_output=True, text=True, timeout=120)
                return StepResult(success=True,
                                  output={"returncode": out.returncode,
                                          "stdout": out.stdout[-4000:],
                                          "stderr": out.stderr[-2000:]},
                                  metadata={"repo": self.meta["repo"],
                                            "script": script},
                                  finished_at=time.time())
            except Exception as e:
                return StepResult(success=False, error=str(e)[:200],
                                  finished_at=time.time())

        return StepResult(success=False,
                          error=f"acção desconhecida: {action} "
                                f"(inventory | search_code | run_script)",
                          finished_at=time.time())

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        ok = result.success
        return VerificationResult(passed=ok,
                                  checks=[{"name": "repo_tool_success", "passed": ok}],
                                  notes=f"repo {self.meta.get('repo')}")


class CapabilityDiscovery:
    """Descobre repositórios GitHub e transforma-os em capabilities TOOL."""

    def __init__(self, registry, work_dir: str | Path = "friday_workspace",
                 permissions=None, logger=None):
        self.registry = registry
        self.work_dir = Path(work_dir)
        self.repos_dir = self.work_dir / "discovered_repos"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.work_dir / "capability_discovery.json"
        self.permissions = permissions
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))

    # ------------------------------------------------------------------ #
    def discover(self, repo_url: str) -> dict[str, Any]:
        """Clona (shallow), inspeciona e registra um repo como capability."""
        slug = re.sub(r"[^\w\-.]+", "_",
                      repo_url.rstrip("/").split("/")[-1]).lower().strip("_")
        if not slug:
            return {"ok": False, "error": "URL inválida"}
        capability_name = f"gh_{slug}"
        if self.registry.get(capability_name) is not None:
            return {"ok": True, "already_registered": True, "capability": capability_name}

        dest = self.repos_dir / slug
        if not dest.exists():
            self.logger(f"[discovery] a clonar {repo_url} (shallow)...")
            try:
                subprocess.run(["git", "clone", "--depth", "1", repo_url, str(dest)],
                               capture_output=True, text=True, timeout=300, check=True)
            except subprocess.CalledProcessError as e:
                return {"ok": False, "error": f"git clone falhou: "
                                              f"{(e.stderr or '')[-200:]}"}

        meta = self._inspect(dest, repo_url, capability_name)
        tool = _GitHubRepoTool(meta, self.permissions, self.logger)
        from .types import CapabilityImpl  # noqa — compat
        self.registry.register(Capability(
            name=capability_name,
            category=CapabilityCategory.TOOL,
            description=tool.description,
            impl=tool,
            tags=["github", "discovered", slug],
        ))
        self._index(meta)
        self.logger(f"[discovery] capability registada: {capability_name}")
        return {"ok": True, "capability": capability_name, **meta}

    # ------------------------------------------------------------------ #
    def _inspect(self, path: Path, repo_url: str,
                 capability_name: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "capability_name": capability_name,
            "repo": repo_url,
            "path": str(path),
            "discovered_at": time.time(),
            "language": None, "license": None, "description": "",
            "entry_points": [], "install": None, "scripts": [],
        }
        # README
        for cand in ("README.md", "readme.md", "README.rst", "README"):
            p = path / cand
            if p.exists():
                text = p.read_text(encoding="utf-8", errors="ignore")[:6000]
                m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                meta["description"] = (m.group(1) if m else "repo GitHub")[:140]
                for lic in ("MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "MPL-2.0"):
                    if lic.lower() in text.lower():
                        meta["license"] = lic
                        break
                break
        # pyproject / setup
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            meta["language"] = "python"
            meta["entry_points"].append("pip install -e .")
            try:
                text = pyproject.read_text(encoding="utf-8", errors="ignore")
                if "license" in text.lower():
                    m = re.search(r'license\s*=\s*[{"]\s*text?\s*=\s*"?([\w\-.]+)', text)
                    if m:
                        meta["license"] = meta["license"] or m.group(1)
            except Exception:
                pass
        if (path / "setup.py").exists() or (path / "setup.cfg").exists():
            meta["language"] = "python"
            meta["entry_points"].append("pip install -e .")
        if (path / "package.json").exists():
            meta["language"] = "javascript"
            meta["entry_points"].append("npm install")
            try:
                pkg = json.loads((path / "package.json").read_text())
                meta["description"] = meta["description"] or pkg.get("description", "")
                meta["license"] = meta["license"] or pkg.get("license")
                for s in (pkg.get("scripts") or {}):
                    meta["scripts"].append(f"npm run {s}")
            except Exception:
                pass
        if (path / "requirements.txt").exists():
            meta["install"] = "pip install -r requirements.txt"
        # scripts shell executáveis
        for sh in sorted(path.glob("*.sh"))[:8]:
            meta["scripts"].append(sh.name)
        return meta

    def _index(self, meta: dict[str, Any]):
        try:
            idx = json.loads(self.index_path.read_text()) \
                if self.index_path.exists() else {}
            idx[meta["capability_name"]] = meta
            self.index_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
        except Exception:
            pass

    def list_discovered(self) -> list[dict[str, Any]]:
        try:
            idx = json.loads(self.index_path.read_text()) \
                if self.index_path.exists() else {}
            return list(idx.values())
        except Exception:
            return []
