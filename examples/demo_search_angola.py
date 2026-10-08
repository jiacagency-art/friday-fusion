"""DEMO: FRIDAY — pesquisa empresas de IA em Angola."""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from friday_core import Friday


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   JIAC FRIDAY — Demo End-to-End                              ║
║                                                              ║
║   Objetivo: pesquisar empresas de IA em Angola               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    friday = Friday(work_dir="friday_workspace")

    caps = friday.capabilities()
    print(f"Capabilities registadas: {caps['total']}")
    print(f"  Funcionais (healthy): {caps['healthy']}")
    print(f"  Por categoria:")
    for cat, n in caps["by_category"].items():
        print(f"    {cat:12s}: {n}")
    print()

    objectives = [
        "pesquisa empresas de inteligência artificial em Angola",
        "encontra startups de tecnologia em Luanda",
    ]

    tasks = []
    for obj in objectives:
        task = friday.run(obj)
        tasks.append(task)
        print()

    if tasks:
        print("┌── ESTADO FINAL DA PRIMEIRA TAREFA ──")
        status = friday.status(tasks[0].id)
        if status:
            print(f"│ ID: {status['id']}")
            print(f"│ Status: {status['status']}")
            print(f"│ Steps:")
            for s in status["steps"]:
                print(f"│   [{s['status']}] {s['capability']}: {s['description']}")
        print("└──────────────────────────────────────")

    outputs_dir = Path("friday_workspace/outputs").resolve()
    print(f"\nArtefactos em: {outputs_dir}")
    if outputs_dir.exists():
        for f in outputs_dir.iterdir():
            print(f"  - {f.name} ({f.stat().st_size} bytes)")

    print("\nDemo completo. ✓")


if __name__ == "__main__":
    main()
