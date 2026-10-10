"""
FRIDAY Permission System
========================
Sistema de permissões do JIAC FRIDAY (visão §29).

Níveis de acção (do mais seguro ao mais crítico):
    READ      → ler, pesquisar, observar (sem alterar nada)
    ANALYZE   → processar dados localmente, gerar estatísticas
    PREPARE   → criar documentos, rascunhos, artefactos locais
    EXECUTE   → executar acções reais (editar ficheiros, publicar, automatizar browser)
    CRITICAL  → enviar email, contactar pessoas, gastar dinheiro, comprometer a JIAC

Regras:
- Cada capability declara o nível mínimo que exige.
- O sistema compara com a política carregada (policy JSON no workspace).
- Níveis acima do permitido exigem aprovação humana (approval callback).
- Toda decisão é registada (audit log) em SQLite/JSON.
- Nunca executa CRITICAL sem aprovação explícita, mesmo se a policy permitir
  (double-lock da visão: "respeitar as regras definidas").
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class PermissionLevel(str, Enum):
    READ = "read"
    ANALYZE = "analyze"
    PREPARE = "prepare"
    EXECUTE = "execute"
    CRITICAL = "critical"


_ORDER: list[str] = [lv.value for lv in PermissionLevel]


def level_of(x: str | PermissionLevel) -> PermissionLevel:
    if isinstance(x, PermissionLevel):
        return x
    try:
        return PermissionLevel(str(x).lower().strip())
    except ValueError:
        return PermissionLevel.EXECUTE  # conservador: trata desconhecido como perigoso


def at_least(action: str | PermissionLevel, minimum: str | PermissionLevel) -> bool:
    """True se `action` é >= `minimum` na escala de perigo."""
    return _ORDER.index(level_of(action).value) >= _ORDER.index(level_of(minimum).value)


DEFAULT_POLICY: dict[str, Any] = {
    # teto absoluto: nada acima de CRITICAL; CRITICAL em si exige aprovação humana
    "max_allowed": "critical",
    # níveis que exigem aprovação humana (double-lock da visão §29)
    "require_approval": ["critical"],
    # overrides por capability (ex.: "email_send": "prepare")
    "capability_overrides": {},
    # modos: "auto" (só critical pergunta), "confirm" (execute+ pergunta), "locked" (nada)
    "mode": "auto",
}


@dataclass
class PermissionDecision:
    allowed: bool = False
    level: PermissionLevel = PermissionLevel.EXECUTE
    requires_approval: bool = False
    reason: str = ""
    policy_max: PermissionLevel = PermissionLevel.EXECUTE
    approved_by: Optional[str] = None
    decided_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "level": self.level.value,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
            "policy_max": self.policy_max.value,
            "approved_by": self.approved_by,
        }


class PermissionSystem:
    """
    Centraliza decisões de permissão do FRIDAY.

    Uso:
        perms = PermissionSystem(work_dir)
        decision = perms.check("email_send", "email_send", requester="orchestrator")
        if not decision.allowed: ...
        if decision.requires_approval:
            approved = perms.request_approval("Enviar email a X?", task_id)
    """

    def __init__(
        self,
        work_dir: str | Path = "friday_workspace",
        policy: Optional[dict[str, Any]] = None,
        approval_callback: Optional[Callable[[str, dict[str, Any]], bool]] = None,
    ):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.policy_path = self.work_dir / "permissions_policy.json"
        self.audit_path = self.work_dir / "permissions_audit.jsonl"
        self.policy = dict(DEFAULT_POLICY)
        if self.policy_path.exists():
            try:
                self.policy.update(json.loads(self.policy_path.read_text(encoding="utf-8")))
            except Exception:
                pass
        if policy:
            self.policy.update(policy)
        self._save_policy()
        self.approval_callback = approval_callback

    # ------------------------------------------------------------------ #
    def _save_policy(self):
        self.policy_path.write_text(
            json.dumps(self.policy, indent=2, ensure_ascii=False), encoding="utf-8")

    def set_policy(self, **kwargs):
        self.policy.update(kwargs)
        self._save_policy()

    def set_capability_level(self, capability: str, max_level: str):
        """Define o nível máximo permitido para uma capability específica."""
        self.policy.setdefault("capability_overrides", {})[capability] = level_of(max_level).value
        self._save_policy()

    # ------------------------------------------------------------------ #
    def check(self, action: str, capability: str = "",
              requester: str = "orchestrator") -> PermissionDecision:
        """
        Decide se uma acção pode ser executada.
        action: nível da acção concreta (ex.: nível declarado da capability/step)
        """
        lvl = level_of(action)
        policy_max = level_of(self.policy.get("max_allowed", "execute"))
        override = (self.policy.get("capability_overrides") or {}).get(capability)
        cap_max = level_of(override) if override else policy_max
        mode = str(self.policy.get("mode", "auto")).lower()

        decision = PermissionDecision(level=lvl, policy_max=cap_max)

        if mode == "locked":
            decision.allowed = False
            decision.reason = "policy em modo locked — nenhuma acção executável"
            self.audit(decision, action, capability, requester)
            return decision

        if _ORDER.index(lvl.value) > _ORDER.index(cap_max.value):
            decision.allowed = False
            decision.reason = (
                f"acção '{lvl.value}' excede o permitido "
                f"(máx '{cap_max.value}' para {capability or 'sistema'})")
            self.audit(decision, action, capability, requester)
            return decision

        needs_approval = any(
            at_least(lvl, PermissionLevel(ra))
            for ra in (self.policy.get("require_approval") or [])
        )
        if mode == "confirm":
            needs_approval = needs_approval or at_least(lvl, PermissionLevel.EXECUTE)
        decision.requires_approval = needs_approval
        decision.allowed = True
        decision.reason = "ok"

        if needs_approval:
            approved = self.request_approval(
                f"FRIDAY pede aprovação para acção {lvl.value} via '{capability}'",
                {"action": action, "capability": capability, "requester": requester},
            )
            if not approved:
                decision.allowed = False
                decision.reason = "aprovação humana negada"
            else:
                decision.approved_by = "human"
        self.audit(decision, action, capability, requester)
        return decision

    # ------------------------------------------------------------------ #
    def request_approval(self, question: str, context: dict[str, Any]) -> bool:
        """
        Pede aprovação humana.
        - Se existe approval_callback → usa-o (dashboard/CLI liga aqui).
        - Em modo headless sem callback → NÃO aprova (falha segura).
        """
        if self.approval_callback is not None:
            try:
                return bool(self.approval_callback(question, context))
            except Exception:
                return False
        return False

    # ------------------------------------------------------------------ #
    def audit(self, decision: PermissionDecision, action: str,
              capability: str, requester: str):
        entry = {
            "ts": time.time(),
            "action": action,
            "capability": capability,
            "requester": requester,
            **decision.to_dict(),
        }
        try:
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def recent_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        lines = self.audit_path.read_text(encoding="utf-8").strip().splitlines()
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
