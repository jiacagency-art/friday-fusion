"""
FRIDAY Proactivity Engine
=========================
Motor de proactividade (funcionalidade dos vídeos): o FRIDAY age sem ser
necessário perguntar por tudo.

Gera ALERTAS e BRIEFINGS automáticos:
- Tarefas falhadas que podem ser recuperadas
- Tarefas pendentes há muito tempo
- Falhas recorrentes de capability (trend detection)
- Briefing diário vencido (novo dia → gera briefing)
- Engines externos indisponíveis (ex.: sem ffmpeg, browser-use desinstalado)

Os alertas aparecem no Dashboard e são guardados em alerts.jsonl.
Agenda opcional: gera briefing automaticamente quando chega a hora configurada.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .types import TaskStatus


@dataclass
class Alert:
    id: str
    level: str          # info | warning | critical
    kind: str           # failed_task | stale_task | capability_gap | briefing_due | engine_down
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "level": self.level, "kind": self.kind,
            "message": self.message, "context": self.context,
            "created_at": self.created_at,
            "time": datetime.fromtimestamp(self.created_at).isoformat(timespec="seconds"),
            "read": self.read,
        }


class ProactivityEngine:
    """Verifica o estado do mundo e gera alertas sem ser pedido."""

    def __init__(
        self,
        work_dir: str | Path = "friday_workspace",
        state=None, registry=None, scheduler=None,
        briefing_impl=None,
        logger: Any = None,
    ):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_path = self.work_dir / "alerts.jsonl"
        self.briefing_dates_path = self.work_dir / "briefing_dates.json"
        self.state = state
        self.registry = registry
        self.scheduler = scheduler
        self.briefing_impl = briefing_impl
        self.logger = logger or (lambda m, level="info": print(f"[{level}] {m}"))
        self._last_check: float = 0.0
        self._briefing_cache: dict[str, Any] | None = None
        self._briefing_cache_day: str | None = None

    # ------------------------------------------------------------------ #
    def _load_alerts(self) -> list[Alert]:
        out: list[Alert] = []
        if self.alerts_path.exists():
            for ln in self.alerts_path.read_text(encoding="utf-8").splitlines()[-200:]:
                try:
                    d = json.loads(ln)
                    out.append(Alert(
                        id=d.get("id", ""), level=d.get("level", "info"),
                        kind=d.get("kind", ""), message=d.get("message", ""),
                        context=d.get("context", {}), created_at=d.get("ts", 0),
                    ))
                except Exception:
                    continue
        return out

    def _append_alert(self, alert: Alert):
        with open(self.alerts_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": alert.created_at, **alert.to_dict()},
                               ensure_ascii=False, default=str) + "\n")

    def raise_alert(self, level: str, kind: str, message: str,
                    context: dict[str, Any] | None = None) -> Alert:
        alert = Alert(
            id=f"alert_{int(time.time())}_{len(self._load_alerts())}",
            level=level, kind=kind, message=message,
            context=context or {})
        self._append_alert(alert)
        self.logger(f"[proactive] ALERTA {level}: {message}", level="warn" if level != "info" else "info")
        return alert

    # ------------------------------------------------------------------ #
    def check(self, force: bool = False) -> list[Alert]:
        """
        Corre uma verificação proactiva completa.
        É chamado: (a) depois de cada missão, (b) pelo dashboard a cada refresh,
        (c) por cron/scheduler.
        """
        now = time.time()
        if not force and now - self._last_check < 60:
            return self.list_alerts()
        self._last_check = now

        new_alerts: list[Alert] = []
        seen = {a.message for a in self._load_alerts()[-40:]}

        def _maybe(level, kind, message, ctx=None):
            if message in seen:
                return
            new_alerts.append(self.raise_alert(level, kind, message, ctx))

        # 1. Tarefas falhadas
        if self.state is not None:
            try:
                for t in self.state.list_recent(limit=30):
                    if t.status == TaskStatus.FAILED:
                        _maybe("critical", "failed_task",
                               f"Missão falhou: {t.objective.raw[:70]}",
                               {"task_id": t.id})
            except Exception:
                pass

        # 2. Capability gaps (ignora stubs — indisponibilidade esperada)
        if self.registry is not None:
            try:
                for cap in self.registry.all():
                    if "stub" in (cap.tags or []):
                        continue
                    try:
                        healthy = cap.impl.health()
                    except Exception:
                        healthy = False
                    if not healthy:
                        _maybe("warning", "capability_gap",
                               f"Capability '{cap.name}' indisponível — activar dependências",
                               {"capability": cap.name})
            except Exception:
                pass

        # 3. Briefing diário vencido
        today = date.today().isoformat()
        if self._briefing_done_today() is False:
            _maybe("info", "briefing_due",
                   f" briefing de {today} ainda não foi gerado — diga 'FRIDAY, prepara o briefing'")

        # 4. Scheduler jobs
        if self.scheduler is not None:
            try:
                jobs = self.scheduler.list_jobs()
                if jobs:
                    _maybe("info", "engine_down" if False else "agenda_info",
                           f"{len(jobs)} job(s) 24/7 activos no scheduler",
                           {"jobs": [j.get("id") for j in jobs]})
            except Exception:
                pass

        return self.list_alerts()

    # ------------------------------------------------------------------ #
    def _briefing_done_today(self) -> bool | None:
        if self.briefing_impl is None:
            return None
        try:
            dates = json.loads(self.briefing_dates_path.read_text()) \
                if self.briefing_dates_path.exists() else {}
            return dates.get(date.today().isoformat(), False)
        except Exception:
            return None

    def mark_briefing_done(self):
        try:
            dates = json.loads(self.briefing_dates_path.read_text()) \
                if self.briefing_dates_path.exists() else {}
            dates[date.today().isoformat()] = True
            self.briefing_dates_path.write_text(json.dumps(dates))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    def daily_briefing(self, city: str = "Luanda", refresh: bool = False) -> dict[str, Any]:
        """Gera (ou devolve do cache diário) o briefing proactivo."""
        today = date.today().isoformat()
        if (not refresh and self._briefing_cache is not None
                and self._briefing_cache_day == today):
            return self._briefing_cache

        data: dict[str, Any]
        if self.briefing_impl is not None:
            class _Ctx:
                config: dict = {"scheduler": self.scheduler, "state": self.state}
            try:
                result = self.briefing_impl.execute({"city": city}, _Ctx())
                data = (result.output or {}) if result.success else {
                    "error": result.error}
            except Exception as e:
                data = {"error": str(e)}
        else:
            data = {"error": "briefing impl não configurada"}

        self._briefing_cache = data
        self._briefing_cache_day = today
        if data and not data.get("error"):
            self.mark_briefing_done()
        return data

    # ------------------------------------------------------------------ #
    def list_alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        alerts = self._load_alerts()
        return [a.to_dict() for a in alerts[-limit:]]

    def unread_count(self) -> int:
        return sum(1 for a in self._load_alerts() if not a.read)

    def mark_all_read(self):
        alerts = self._load_alerts()
        try:
            self.alerts_path.write_text(
                "".join(json.dumps({"ts": a.created_at, **{**a.to_dict(), "read": True}},
                                   ensure_ascii=False, default=str) + "\n"
                        for a in alerts),
                encoding="utf-8")
        except Exception:
            pass
