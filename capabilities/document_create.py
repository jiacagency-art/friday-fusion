"""Document Create Capability — Markdown / JSON / TXT."""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any
from friday_core.types import (
    CapabilityCategory, CapabilityImpl, ExecutionContext,
    StepResult, VerificationResult,
)


class DocumentCreateCapability(CapabilityImpl):
    name = "documents_create"
    category = CapabilityCategory.DOCUMENTS
    description = "Gera documentos Markdown / JSON / TXT"

    def __init__(self, output_dir: str | Path = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, inputs: dict[str, Any], ctx: ExecutionContext) -> StepResult:
        path = inputs.get("path")
        fmt = (inputs.get("format") or "markdown").lower()
        title = inputs.get("title", "FRIDAY Report")
        content = inputs.get("content")
        meta = inputs.get("meta", {})
        if not path:
            return StepResult(success=False, error="path é obrigatório")
        try:
            full_path = self.output_dir / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "json":
                text = json.dumps(content, ensure_ascii=False, indent=2)
            elif fmt == "txt":
                text = self._to_text(content)
            else:
                text = self._to_markdown(title, content, meta)
            full_path.write_text(text, encoding="utf-8")
            return StepResult(
                success=True,
                output={"path": str(full_path), "size_bytes": len(text.encode("utf-8"))},
                artifacts=[{"type": "file", "path": str(full_path), "format": fmt}],
                metadata={"format": fmt, "title": title},
                finished_at=time.time(),
            )
        except Exception as e:
            return StepResult(success=False, error=str(e), finished_at=time.time())

    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False, checks=[{
                "name": "execution_success", "passed": False, "error": result.error
            }])
        path = Path(result.output["path"])
        checks = [
            {"name": "file_exists", "passed": path.exists()},
            {"name": "file_non_empty", "passed": path.exists() and path.stat().st_size > 0},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks), checks=checks)

    def _to_markdown(self, title: str, content: Any, meta: dict) -> str:
        lines = [f"# {title}", ""]
        if meta:
            lines.append("> Gerado por JIAC FRIDAY")
            for k, v in meta.items():
                lines.append(f"> **{k}**: {v}")
            lines.append("")
        if isinstance(content, str):
            lines.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    title_str = item.get("title") or item.get("name") or "—"
                    lines.append(f"## {title_str}")
                    for k, v in item.items():
                        if k in ("title", "name"):
                            continue
                        lines.append(f"- **{k}**: {v}")
                    lines.append("")
                else:
                    lines.append(f"- {item}")
        elif isinstance(content, dict):
            for k, v in content.items():
                lines.append(f"## {k}")
                lines.append(str(v))
                lines.append("")
        else:
            lines.append(str(content))
        return "\n".join(lines)

    def _to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(x) for x in content)
        return json.dumps(content, ensure_ascii=False, indent=2)
