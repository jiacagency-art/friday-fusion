"""DEMO: Scheduler — mostra tarefas agendadas do FRIDAY."""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k and k not in os.environ:
                    os.environ[k] = v

load_env()

from friday_core import Friday


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   JIAC FRIDAY — Demo Scheduler                               ║
║                                                              ║
║   Mostra o scheduler com tarefas recorrentes.                ║
║   Não executa as tarefas (só mostra agendamento).            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    friday = Friday(work_dir="friday_scheduler_demo")

    if not friday.scheduler.is_available():
        print("❌ APScheduler não instalado. Instalar com: pip install apscheduler")
        return

    print("✓ APScheduler disponível")
    print()

    # Configurar schedule default
    print("=== Configurando schedule default ===")
    friday.scheduler.setup_default_schedule()
    print()

    # Listar jobs
    print("=== Jobs agendados ===")
    jobs = friday.scheduler.list_jobs()
    for j in jobs:
        print(f"\n  Job: {j['id']}")
        print(f"  Trigger: {j['trigger']}")
        print(f"  Próxima execução: {j['next_run']}")
    print()

    # Adicionar job customizado para daqui a 1 minuto (para teste)
    from datetime import datetime, timedelta
    print("=== Adicionando job de teste (daqui a 30s) ===")
    run_time = datetime.now() + timedelta(seconds=30)
    friday.scheduler.scheduler.add_job(
        func=lambda: print(f"\n>>> JOB DE TESTE EXECUTADO às {datetime.now()}"),
        trigger="date",
        run_date=run_time,
        id="test_job",
    )
    print(f"Job de teste agendado para: {run_time.strftime('%H:%M:%S')}")
    print()

    # Esperar o job executar
    print("=== Esperando 35s para o job de teste executar... ===")
    time.sleep(35)

    print()
    print("=== Jobs log ===")
    for entry in friday.scheduler.jobs_log:
        print(f"  {entry}")

    friday.scheduler.stop()
    print("\nDemo Scheduler completo. ✓")


if __name__ == "__main__":
    main()
