"""
JIAC FRIDAY v1.0 — Demo completo SEM API keys
=============================================
Demonstra TODOS os engines novos da visão a funcionar de verdade:
  1. Briefing proativo   (clima + notícias + IA + resumo)
  2. Editor de vídeo     (gera vídeo de teste → storyboard → corte → vertical → legendas)
  3. Data Engine         (análise real de CSV com estatísticas)
  4. Agent-Reach real    (prospecção comercial → lista CRM CSV)
  5. Email honesto       (rascunho .eml sem SMTP configurado)
  6. Permission System   (audit trail visível)
  7. Fast Execution      (ondas paralelas + cache + métricas JEV)

Executar:  python examples/demo_v1_completo.py
"""

from __future__ import annotations

import csv
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from friday_core import Friday  # noqa: E402

WS = Path("demo_workspace_v1")


def make_test_video(path: Path) -> bool:
    """Gera um vídeo de teste de 20s com ffmpeg (barra de cores + tom)."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "testsrc=duration=20:size=1280x720:rate=24",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
             "-shortest", str(path)],
            capture_output=True, text=True, timeout=120, check=True)
        return True
    except Exception as e:
        print(f"[demo] ffmpeg falhou: {e}")
        return False


def make_test_csv(path: Path):
    """CSV de vendas JIAC para o Data Engine."""
    random.seed(42)
    sectores = ["hotelaria", "banca", "retalho", "energia", "telecom"]
    rows = []
    for i in range(120):
        sector = random.choice(sectores)
        rows.append({
            "mes": random.choice(["jan", "fev", "mar", "abr"]),
            "sector": sector,
            "leads": random.randint(5, 60),
            "vendas": random.randint(0, 25),
            "receita_kz": random.randint(500, 9000),
        })
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def main():
    print("\n" + "═" * 66)
    print("  JIAC FRIDAY v1.0 — DEMO COMPLETO (sem API keys)")
    print("═" * 66)

    friday = Friday(work_dir=str(WS))

    # prepara ficheiros de teste
    WS.mkdir(parents=True, exist_ok=True)
    video_path = WS / "video.mp4"
    csv_path = WS / "dados.csv"
    if not video_path.exists():
        print("[demo] a gerar vídeo de teste 20s...")
        make_test_video(video_path)
    make_test_csv(csv_path)

    missions = [
        # 1. BRIEFING PROATIVO
        "prepara o briefing de hoje",
        # 2. EDITOR DE VÍDEO agentivo (storyboard ∥ corte ∥ vertical em paralelo)
        "corta o video.mp4 em 8 segundos e cria versão vertical para TikTok",
        # 3. DATA ENGINE
        "analisa o dados.csv com estatísticas",
        # 4. AGENT-REACH real → CRM
        "encontra empresas angolanas que precisem de automação e organiza no CRM",
        # 5. EMAIL honesto (sem SMTP → rascunho)
        "escreve email para geral@jiac.ao com o relatório do FRIDAY",
    ]

    results = []
    for m in missions:
        print(f"\n{'─'*66}\n▶ MISSÃO: {m}\n{'─'*66}")
        t0 = time.time()
        task = friday.run(m)
        dt = time.time() - t0
        ok = task.status.value == "completed"
        results.append((m, ok, dt))
        time.sleep(0.3)

    # ---- proactivity + permission audit ----
    print(f"\n{'─'*66}\n▶ VERIFICAÇÃO PROACTIVA\n{'─'*66}")
    for a in friday.proactive_check()[:6]:
        print(f"  [{a['level']}] {a['message'][:80]}")

    print(f"\n{'─'*66}\n▶ AUDIT DE PERMISSÕES (últimas decisões)\n{'─'*66}")
    for entry in friday.permissions.recent_audit(6):
        print(f"  {entry['capability'] or '—':20s} "
              f"acção={entry['action']:10s} permitido={entry['allowed']}")

    # ---- resumo final ----
    print(f"\n{'═'*66}\n  RESUMO DO DEMO\n{'═'*66}")
    for m, ok, dt in results:
        print(f"  {'✓' if ok else '✗'} [{dt:5.1f}s] {m}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  {passed}/{len(results)} missões concluídas")

    fast = getattr(friday.executor, "last_metrics", None)
    if fast:
        s = fast.summary()
        print(f"  JEV: {s['parallel_waves']} ondas paralelas · "
              f"{s['cache_hits']} cache hits · p50 {s['latency_p50_s']}s")

    print(f"\n  Artefactos em: {WS}/outputs/")
    for p in sorted((WS / "outputs").rglob("*")):
        if p.is_file() and p.stat().st_size > 0:
            print(f"    · {p.relative_to(WS)}  ({p.stat().st_size:,} bytes)")

    print(f"\n  Dashboard:  python -m friday_core.dashboard --workdir {WS}")
    print("═" * 66 + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    import os
    _rc = main()
    # força saída limpa (ffmpeg pode deixar threads no grupo do processo)
    sys.stdout.flush()
    os._exit(_rc if isinstance(_rc, int) else 0)
