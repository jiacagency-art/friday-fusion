"""
FRIDAY Scheduler
================
Sistema de agendamento de tarefas recorrentes do FRIDAY.

Usa APScheduler para correr tarefas em background:
- Relatório diário de mercado (08:00)
- Verificação de leads (17:00)
- Análise semanal (domingo 10:00)

O scheduler corre num thread separado, não bloqueia o orchestrator.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


class FridayScheduler:
    """
    Scheduler de tarefas recorrentes do FRIDAY.

    Uso:
        scheduler = FridayScheduler(friday_instance)
        scheduler.start()
        # ... FRIDAY corre tarefas agendadas em background ...
        scheduler.stop()
    """

    def __init__(self, friday_instance=None):
        self.friday = friday_instance
        self.scheduler: Optional[Any] = None
        self._lock = threading.Lock()
        self.jobs_log: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return APSCHEDULER_AVAILABLE

    def start(self) -> bool:
        if not APSCHEDULER_AVAILABLE:
            print("[Scheduler] APScheduler não instalado — instalar com: pip install apscheduler")
            return False
        with self._lock:
            if self.scheduler is not None:
                return True
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            print("[Scheduler] Iniciado")
            return True

    def stop(self):
        with self._lock:
            if self.scheduler:
                self.scheduler.shutdown(wait=False)
                self.scheduler = None
                print("[Scheduler] Parado")

    def add_daily_job(self, name: str, hour: int, minute: int,
                      objective: str, day_of_week: str = "*") -> bool:
        """Adiciona uma tarefa diária."""
        if not self.scheduler:
            return False
        self.scheduler.add_job(
            func=self._run_objective,
            trigger=CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week),
            id=name,
            args=[name, objective],
            replace_existing=True,
        )
        print(f"[Scheduler] Job '{name}' agendado: {day_of_week} {hour:02d}:{minute:02d} — {objective[:60]}")
        return True

    def add_weekly_job(self, name: str, day_of_week: str, hour: int, minute: int,
                       objective: str) -> bool:
        """Adiciona uma tarefa semanal."""
        return self.add_daily_job(name, hour, minute, objective, day_of_week=day_of_week)

    def list_jobs(self) -> list[dict[str, Any]]:
        if not self.scheduler:
            return []
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger),
            })
        return jobs

    def _run_objective(self, name: str, objective: str):
        """Executa um objective do FRIDAY (chamado pelo scheduler)."""
        started = datetime.now()
        print(f"\n[Scheduler] ▶ Job '{name}' iniciado às {started}")
        print(f"[Scheduler]   Objective: {objective}")

        self.jobs_log.append({
            "name": name, "objective": objective,
            "started_at": started.isoformat(), "status": "running",
        })

        if self.friday is None:
            print(f"[Scheduler]   (sem instância FRIDAY — log apenas)")
            self.jobs_log[-1]["status"] = "skipped_no_friday"
            return

        try:
            task = self.friday.run(objective)
            self.jobs_log[-1].update({
                "status": task.status.value,
                "task_id": task.id,
                "finished_at": datetime.now().isoformat(),
            })
            print(f"[Scheduler] ✓ Job '{name}' terminado: {task.status.value}")
        except Exception as e:
            self.jobs_log[-1].update({
                "status": "error",
                "error": str(e),
                "finished_at": datetime.now().isoformat(),
            })
            print(f"[Scheduler] ✗ Job '{name}' erro: {e}")

    def setup_default_schedule(self) -> bool:
        """
        Configura as tarefas default do FRIDAY:
        - 08:00 diário: relatório de mercado Angola
        - 17:00 diário: verificar leads
        - Domingo 10:00: análise semanal
        """
        if not self.start():
            return False

        self.add_daily_job(
            "daily_market_report",
            hour=8, minute=0,
            objective="prepara relatório diário do mercado angolano: principais notícias, oportunidades e riscos",
        )
        self.add_daily_job(
            "daily_leads_check",
            hour=17, minute=0,
            objective="verifica leads do Agent-Reach e prepara relatório de follow-up",
        )
        self.add_weekly_job(
            "weekly_opportunities_analysis",
            day_of_week="sun", hour=10, minute=0,
            objective="análise semanal de oportunidades de negócio para a JIAC",
        )
        return True
