"""
FRIDAY Communication Engine
===========================
Email real (visão §14) com regra de segurança dupla:
- Se SMTP configurado (env SMTP_HOST/SMTP_USER/SMTP_PASS) → envia de verdade
  (acção CRITICAL → exige aprovação via Permission System).
- Se NÃO configurado → guarda rascunho .eml no workspace (acção PREPARE),
  para o utilizador enviar mais tarde. NUNCA finge que enviou.

Também suporta "draft" forçado e registos de comunicação em JSON.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, StepResult, VerificationResult,
)


class EmailCapability(CapabilityImpl):
    name = "email_send"
    category = CapabilityCategory.COMMUNICATION
    description = ("Communication Engine — envia email real via SMTP "
                   "(ou guarda rascunho .eml se SMTP não configurado)")

    def __init__(self, output_dir: str | Path = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def health(self) -> bool:
        return True

    def action_level(self, inputs: dict[str, Any]) -> str:
        """
        Nível real da acção (visão §29):
        - a enviar de verdade (SMTP configurado) → CRITICAL (pede aprovação)
        - rascunho .eml local                    → PREPARE (seguro)
        """
        will_send = self.smtp_configured() and not inputs.get("draft", False)
        return "critical" if will_send else "prepare"

    # ------------------------------------------------------------------ #
    @staticmethod
    def smtp_configured() -> bool:
        return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))

    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        started = time.time()
        to = str(inputs.get("to", "")).strip()
        subject = str(inputs.get("subject", "Mensagem do FRIDAY")).strip()
        body = str(inputs.get("body", "")).strip()
        force_draft = bool(inputs.get("draft", False))
        html = bool(inputs.get("html", False))

        if not to:
            return StepResult(success=False,
                              error="destinatário 'to' obrigatório",
                              finished_at=time.time())
        if not body:
            return StepResult(success=False, error="corpo 'body' vazio",
                              finished_at=time.time())

        msg = MIMEMultipart("alternative" if html else "mixed")
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER",
                                                                    "friday@jiac.local"))
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))

        sent = False
        mode = "draft"
        detail: dict[str, Any] = {}

        smtp_ready = self.smtp_configured() and not force_draft
        if smtp_ready:
            host = os.environ["SMTP_HOST"]
            port = int(os.environ.get("SMTP_PORT", "465"))
            user = os.environ["SMTP_USER"]
            pwd = os.environ.get("SMTP_PASS", "")
            try:
                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=25,
                                              context=ssl.create_default_context())
                else:
                    server = smtplib.SMTP(host, port, timeout=25)
                    server.starttls(context=ssl.create_default_context())
                try:
                    server.login(user, pwd)
                    server.sendmail(msg["From"], [to], msg.as_string())
                finally:
                    server.quit()
                sent = True
                mode = "sent"
                detail["smtp_host"] = host
            except Exception as e:
                mode = "draft_fallback"
                detail["smtp_error"] = f"{type(e).__name__}: {e}"

        # rascunho .eml (sempre guardado como registo)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        draft_path = self.output_dir / f"email_{mode}_{stamp}.eml"
        draft_path.write_bytes(msg.as_bytes())
        log_path = self.output_dir / "communications_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(), "to": to, "subject": subject,
                "mode": mode, "sent": sent, "artifact": str(draft_path),
            }, ensure_ascii=False) + "\n")

        output = {
            "to": to, "subject": subject, "sent": sent, "mode": mode,
            "artifact": str(draft_path), **detail,
            "note": ("email enviado via SMTP ✓" if sent else
                     "SMTP não configurado ou rascunho forçado — "
                     "guardado .eml pronto a enviar (não enviado)"),
        }
        return StepResult(success=True, output=output,
                          artifacts=[{"path": str(draft_path), "kind": "email"}],
                          metadata={"sent": sent, "mode": mode},
                          finished_at=time.time())

    # ------------------------------------------------------------------ #
    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        if not result.success:
            return VerificationResult(passed=False,
                                      checks=[{"name": "success", "passed": False,
                                               "error": result.error}])
        o = result.output or {}
        artifact_ok = Path(o.get("artifact", "")).exists()
        checks = [
            {"name": "artifact_saved", "passed": artifact_ok},
            {"name": "honest_mode", "passed": o.get("mode") in
             ("sent", "draft", "draft_fallback")},
        ]
        return VerificationResult(passed=all(c["passed"] for c in checks),
                                  checks=checks,
                                  notes=("email enviado" if o.get("sent")
                                         else "rascunho guardado (não fingir envio)"))
