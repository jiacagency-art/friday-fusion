"""DEMO: FRIDAY com LLM Router (Gemini) — mostra fallback gracioso."""

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
from friday_core.llm_client import GeminiClient


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   JIAC FRIDAY — Demo LLM Router (Gemini)                     ║
║                                                              ║
║   Mostra o FRIDAY a usar Gemini para parse + plan.           ║
║   Se Gemini indisponível, fallback para regras.              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    client = GeminiClient()
    print(f"GEMINI_API_KEY configurada: {client.is_configured()}")
    if client.is_configured():
        print(f"Modelo: {client.model}")
        print(f"A testar conexão Gemini...")
        healthy = client.health()
        print(f"  Gemini disponível: {'✓ SIM' if healthy else '✗ NÃO (fallback para regras)'}")
    print()

    friday = Friday(work_dir="friday_workspace")

    caps = friday.capabilities()
    print(f"\nCapabilities registadas: {caps['total']}")
    print(f"  Funcionais (healthy): {caps['healthy']}")
    print()

    objectives = [
        "quero saber quem são os principais importadores de café em Angola e prepara uma lista comercial",
        "analisa o mercado de fintech angolano e identifica as 5 maiores oportunidades para a JIAC",
    ]

    tasks = []
    for obj in objectives:
        task = friday.run(obj)
        tasks.append(task)
        print()

    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    for t in tasks:
        status = friday.status(t.id)
        if status:
            completed = sum(1 for s in status["steps"] if s["status"] == "completed")
            total = len(status["steps"])
            print(f"\nTask {t.id}")
            print(f"  Objective: {status['objective'][:70]}...")
            print(f"  Status: {status['status']}")
            print(f"  Steps: {completed}/{total} completed")

    outputs_dir = Path("friday_workspace/outputs").resolve()
    print(f"\n\nArtefactos gerados em: {outputs_dir}")
    if outputs_dir.exists():
        for f in sorted(outputs_dir.iterdir()):
            print(f"  - {f.name} ({f.stat().st_size:,} bytes)")

    print("\nDemo LLM Router completo. ✓")


if __name__ == "__main__":
    main()
