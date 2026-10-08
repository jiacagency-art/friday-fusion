"""
DEMO: Integração Completa (FASE 8)
==================================
Loop end-to-end do FRIDAY:
  Input → Parser → Router → Crew de Agentes → Execution →
  Verify → Self-Improve → Report

Testa com objective complexo sobre mercado angolano de energia.
"""

from __future__ import annotations
import os
import sys
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
║   JIAC FRIDAY — Demo Integração Completa (FASE 8)            ║
║                                                              ║
║   Loop: Input → Parser → Router → Execution →                ║
║         Verify → Self-Improve → Report                       ║
║                                                              ║
║   Objective complexo sobre mercado angolano de energia       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    friday = Friday(work_dir="friday_integration_demo")

    # Mostrar estado do FRIDAY
    print("=== ESTADO DO FRIDAY ===")
    caps = friday.capabilities()
    print(f"Capabilities: {caps['total']} total, {caps['healthy']} healthy")
    print(f"Memory: {'Mem0' if friday.memory.is_mem0_active() else 'SQLite'}")
    print(f"Router: {'LLM (Gemini)' if friday.use_llm else 'regras'}")
    print(f"Scheduler: {'disponível' if friday.scheduler.is_available() else 'indisponível'}")
    print(f"Self-Improvement: ativo")
    print()

    # Objectives de teste (do mais simples ao mais complexo)
    objectives = [
        {
            "level": "simples",
            "text": "pesquisa as 3 maiores empresas de petróleo em Angola",
            "expected_capabilities": ["web_search"],
        },
        {
            "level": "médio",
            "text": "analisa o mercado de telecomunicações de Angola e identifica as 5 maiores oportunidades",
            "expected_capabilities": ["web_search", "documents_create"],
        },
    ]

    results = []
    for obj in objectives:
        print(f"\n{'='*60}")
        print(f"OBJECTIVE ({obj['level']}): {obj['text']}")
        print(f"Expected capabilities: {obj['expected_capabilities']}")
        print(f"{'='*60}")

        task = friday.run(obj["text"])
        results.append({
            "objective": obj["text"],
            "level": obj["level"],
            "status": task.status.value,
            "task_id": task.id,
        })

    # Resumo final
    print(f"\n\n{'='*60}")
    print("RESUMO FINAL DA INTEGRAÇÃO")
    print(f"{'='*60}")
    for r in results:
        print(f"\n  [{r['level'].upper()}] {r['objective'][:60]}")
        print(f"  Status: {r['status']}")
        print(f"  Task ID: {r['task_id']}")

    # Self-improvement summary
    print(f"\n{'='*60}")
    print("SELF-IMPROVEMENT SUMMARY")
    print(f"{'='*60}")
    lessons = friday.self_improvement.get_lessons()
    recoveries = friday.self_improvement.get_recoveries()
    print(f"  Lições aprendidas: {len(lessons)}")
    print(f"  Estratégias de recovery bem-sucedidas: {len(recoveries)}")
    if lessons:
        print(f"\n  Últimas 3 lições:")
        for l in lessons[-3:]:
            print(f"    - [{l.get('error_type', '?')}] {l.get('lesson', '?')[:100]}")

    # Scheduler state
    print(f"\n{'='*60}")
    print("SCHEDULER STATE")
    print(f"{'='*60}")
    if friday.scheduler.is_available():
        print("  ✓ APScheduler disponível")
        print("  (Jobs não iniciados neste demo — ver demo_scheduler.py)")
    else:
        print("  ✗ APScheduler indisponível")

    # Artefactos
    outputs_dir = Path("friday_integration_demo/outputs").resolve()
    print(f"\n{'='*60}")
    print(f"ARTEFACTOS GERADOS ({outputs_dir})")
    print(f"{'='*60}")
    if outputs_dir.exists():
        for f in sorted(outputs_dir.iterdir()):
            print(f"  - {f.name} ({f.stat().st_size:,} bytes)")
    else:
        print("  (nenhum)")

    print(f"\n{'='*60}")
    print("Demo Integração Completa terminado. ✓")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
