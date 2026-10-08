"""DEMO: Self-Improvement — mostra o FRIDAY a aprender com falhas."""

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
║   JIAC FRIDAY — Demo Self-Improvement                        ║
║                                                              ║
║   Mostra o FRIDAY a avaliar tarefas e extrair lições.        ║
║   Faz uma tarefa que vai falhar e vê o FRIDAY aprender.      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    friday = Friday(work_dir="friday_selfimprove_demo")

    # Tarefa 1: vai falhar (capability stub)
    print("=" * 60)
    print("TAREFA 1: Tarefa que vai falhar (usa stub)")
    print("  Objective: 'encontra empresas com Agent-Reach'")
    print("  → Vai usar business_prospect que é STUB")
    print("=" * 60)
    task1 = friday.run("encontra empresas com Agent-Reach")
    print()

    # Tarefa 2: tarefa normal
    print("=" * 60)
    print("TAREFA 2: Tarefa normal (research)")
    print("=" * 60)
    task2 = friday.run("pesquisa empresas de IA em Angola")
    print()

    # Mostrar lições aprendidas
    print("=" * 60)
    print("LIÇÕES APRENDIDAS PELO FRIDAY")
    print("=" * 60)
    lessons = friday.self_improvement.get_lessons()
    print(f"\nTotal de lições: {len(lessons)}")
    for i, l in enumerate(lessons, 1):
        print(f"\n  Lição {i}:")
        print(f"    Capability: {l.get('capability', '?')}")
        print(f"    Tipo de erro: {l.get('error_type', '?')}")
        print(f"    Lição: {l.get('lesson', '?')[:120]}")
        print(f"    Task: {l.get('task_id', '?')}")

    # Mostrar recoveries
    print("\n" + "=" * 60)
    print("ESTRATÉGIAS DE RECOVERY BEM-SUCEDIDAS")
    print("=" * 60)
    recoveries = friday.self_improvement.get_recoveries()
    print(f"\nTotal: {len(recoveries)}")
    for r in recoveries:
        print(f"  - {r.get('capability', '?')}: {r.get('strategy', '?')} "
              f"({r.get('attempts_needed', '?')} tentativas)")

    # Mostrar sugestões para próximo objective
    print("\n" + "=" * 60)
    print("SUGESTÕES PARA PRÓXIMA TAREFA DE RESEARCH")
    print("=" * 60)
    suggestions = friday.self_improvement.suggest_for_objective("pesquisa mercado Angola")
    for s in suggestions:
        print(f"  → {s}")

    print("\nDemo Self-Improvement completo. ✓")


if __name__ == "__main__":
    main()
