"""
JIAC FRIDAY v1.0 — Testes de fumo (smoke tests)
================================================
Corre sem API keys. Alguns testes precisam de ffmpeg + rede.

Executar:  PYTHONPATH=. python tests/test_v1.py
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from friday_core import (  # noqa: E402
    Friday, PermissionSystem, PermissionLevel, at_least, RecoveryEngine,
    classify_error, FastExecutor, ResponseCache, build_waves,
)
from friday_core.objective_parser import parse  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}" + (f" — {extra}" if extra else ""))
    else:
        FAIL += 1
        print(f"  ✗ {name}" + (f" — {extra}" if extra else ""))


def make_test_video(path: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=12:size=640x360:rate=12",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, timeout=90, check=True)


def make_test_csv(path: Path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["sector", "vendas", "receita"])
        for i in range(40):
            w.writerow([["hotel", "banco", "retalho"][i % 3],
                        10 + i % 7, 100 * (i + 1)])


def main():
    tmp = Path(tempfile.mkdtemp(prefix="friday_test_"))
    print(f"\n═  JIAC FRIDAY v1.0 — testes de fumo ({tmp})\n")

    # ---------------- 1. Parser de objectivos ----------------
    print("1. Objective Parser")
    o = parse("prepara o briefing de hoje")
    check("intent briefing", o.intent == "briefing")
    o = parse("corta o video.mp4 em 15 segundos e cria versão vertical")
    check("intent video_edit", o.intent == "video_edit")
    check("source extraído", o.entities.get("source") == "video.mp4",
          str(o.entities.get("source")))
    o = parse("analisa o dados.csv com estatísticas")
    check("intent data_analyze", o.intent == "data_analyze")
    check("path extraído", o.entities.get("path") == "dados.csv")
    o = parse("envia email para chefe@jiac.ao com o relatório")
    check("intent email + destinatário", o.intent == "email"
          and o.entities.get("to") == "chefe@jiac.ao")
    o = parse("encontra empresas que precisem de automação e organiza no CRM")
    check("intent prospect", o.intent == "prospect")

    # ---------------- 2. Router ----------------
    print("2. Universal Router")
    from friday_core import build_default_registry
    reg = build_default_registry(output_dir=tmp / "outputs", use_gpt_researcher=False)
    from friday_core.router import UniversalRouter
    router = UniversalRouter(reg)
    plan = router.route(parse("corta o video.mp4 e cria versão vertical"))
    caps_used = {s.capability for s in plan.steps}
    check("plano de vídeo usa video_editor", caps_used == {"video_editor"},
          f"{len(plan.steps)} steps")
    plan = router.route(parse("encontra empresas para o CRM"))
    check("plano de prospect usa prospect_real",
          plan.steps[0].capability == "prospect_real")

    # ---------------- 3. Permission System ----------------
    print("3. Permission System")
    perms = PermissionSystem(work_dir=tmp / "perm")
    check("escala de níveis", at_least("critical", "execute")
          and not at_least("read", "analyze"))
    d = perms.check("read", "briefing")
    check("read permitido", d.allowed)
    d = perms.check("critical", "email_send")  # sem callback → negado
    check("CRITICAL negado sem aprovação", not d.allowed, d.reason[:40])
    perms.approval_callback = lambda q, c: True
    d = perms.check("critical", "email_send")
    check("CRITICAL permitido com aprovação", d.allowed and d.approved_by == "human")
    perms.set_capability_level("email_send", "prepare")
    d = perms.check("critical", "email_send")
    check("override por capability", not d.allowed)

    # ---------------- 4. Recovery Engine ----------------
    print("4. Recovery Engine")
    check("classifica network", classify_error("ConnectionTimeout: connect") == "network")
    check("classifica rate_limit", classify_error("429 Too Many Requests") == "rate_limit")
    check("classifica missing_cap",
          classify_error("Capability não registada: x") == "missing_cap")
    rec = RecoveryEngine(registry=reg)
    p = rec.plan("s1", "web_search", 1, "connect timeout")
    check("estratégia network=wait_retry", p.strategy == "wait_retry")

    # ---------------- 5. FastExecutor (JEV) ----------------
    print("5. Fast Execution Fabric (JEV)")
    cache = ResponseCache(ttl_seconds=60)
    k = ResponseCache.key("c", {"a": 1})
    cache.put(k, "X")
    hit, val = cache.get(k)
    check("cache put/get", hit and val == "X")
    from friday_core.types import Plan, Step, Objective
    obj = Objective(raw="t", normalized="t", intent="t", entities={})
    plan = Plan(objective_id=obj.id, steps=[
        Step(id="a", description="a", capability="x1", inputs={}),
        Step(id="b", description="b", capability="x2", inputs={}),
        Step(id="c", description="c", capability="x3", inputs={}, depends_on=["a"]),
    ])
    waves = build_waves(plan)
    check("ondas topológicas", len(waves) == 2 and
          {s.id for s in waves[0]} == {"a", "b"}, f"{len(waves)} ondas")

    # ---------------- 6. Friday end-to-end ----------------
    print("6. FRIDAY end-to-end (sem API keys)")
    ws = tmp / "friday_ws"
    friday = Friday(work_dir=str(ws), use_mem0=False)
    make_test_csv(ws / "dados.csv")
    task = friday.run("analisa o dados.csv com estatísticas")
    check("missão de dados completa", task.status.value == "completed",
          f"{len(task.plan.steps)} step")
    out = task.plan.steps[0].result.output if task.plan else {}
    check("estatísticas reais", (out or {}).get("rows") == 40
          and "profile" in out, f"rows={out.get('rows')}")
    md = (ws / "outputs" / "analise_dados.md")
    check("relatório markdown gerado", md.exists() and md.stat().st_size > 200)

    # agentes
    check("agentes criados", len(friday.agent_factory.created) >= 5,
          f"{len(friday.agent_factory.created)} agentes")
    check("registry v1.0 completo", len(friday.registry.all()) >= 28,
          f"{len(friday.registry.all())} capabilities")

    # ---------------- 7. Video editor (se ffmpeg) ----------------
    print("7. Video Editor (ffmpeg)")
    if shutil.which("ffmpeg"):
        make_test_video(ws / "video.mp4")
        task = friday.run("corta o video.mp4 em 5 segundos e cria versão vertical")
        ok = task.status.value == "completed"
        vids = list((ws / "outputs" / "video").glob("*.mp4")) if ok else []
        check("missão de vídeo completa", ok, f"{len(vids)} ficheiros de vídeo")
    else:
        print("  ⊘ ffmpeg não disponível — testes de vídeo saltados")

    # ---------------- 8. Email honesto ----------------
    print("8. Email honesto")
    task = friday.run("escreve email para teste@jiac.ao com o resumo")
    check("email draft completa", task.status.value == "completed")
    emls = list((ws / "outputs").glob("email_*.eml"))
    check("rascunho .eml guardado", len(emls) >= 1, emls[0].name if emls else "")
    sent_check = "sent" in emls[0].read_text(errors="ignore").lower() \
        if emls else False
    check("não finge envio", not sent_check)

    # ---------------- 9. Proactivity ----------------
    print("9. Proactivity Engine")
    alerts = friday.proactive_check()
    check("alertas proactivos gerados", len(alerts) >= 1, f"{len(alerts)} alertas")

    # ---------------- 10. Dashboard ----------------
    print("10. Dashboard")
    from friday_core.dashboard import DashboardServer
    import threading
    srv = DashboardServer(friday, host="127.0.0.1", port=8560)
    srv.start_background()
    time.sleep(1.0)
    import urllib.request
    try:
        html = urllib.request.urlopen("http://127.0.0.1:8560/", timeout=5).read()
        st = json.loads(urllib.request.urlopen(
            "http://127.0.0.1:8560/api/status", timeout=5).read())
        check("dashboard HTML servido", b"FRIDAY" in html, f"{len(html)} bytes")
        check("API status", st.get("version") == "1.0.0")
    except Exception as e:
        check("dashboard acessível", False, str(e)[:60])
    srv.stop()

    print(f"\n═  RESULTADO: {PASS} passaram · {FAIL} falharam\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    import os
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
