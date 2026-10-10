"""
FRIDAY Dashboard — Interface visual unificada
=============================================
"Cartões, alertas e contexto" (funcionalidade dos vídeos da visão).

Servidor web com ZERO dependências (stdlib http.server):
- GET  /                    → interface de cartões (dashboard.html)
- GET  /api/status          → estado do sistema + engines + métricas
- GET  /api/capabilities    → grelha de capabilities
- GET  /api/tasks           → missões recentes
- GET  /api/task/<id>       → detalhe de missão
- GET  /api/briefing        → briefing proactivo (cache diária)
- GET  /api/alerts          → alertas proactivos
- POST /api/objective       → {"objective": "..."} corre missão em background
- POST /api/approve         → {"approve": true/false} aprovação humana

Executar:
    python -m friday_core.dashboard --port 8500
ou programaticamente:
    friday.serve(port=8500)
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_HTML_PATH = Path(__file__).with_name("dashboard.html")


class DashboardServer:
    """Servidor do dashboard do FRIDAY (thread-per-request)."""

    def __init__(self, friday: Any, host: str = "127.0.0.1", port: int = 8500):
        self.friday = friday
        self.host = host
        self.port = port
        self.started_at = time.time()
        self._running = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None
        self._pending_approval: dict[str, Any] | None = None
        self._approval_result: bool | None = None

        friday.permissions.approval_callback = self._request_approval

    # ------------------------------------------------------------------ #
    def _request_approval(self, question: str, context: dict[str, Any]) -> bool:
        """Aprovação humana via dashboard (bloqueia até resposta ou timeout)."""
        self._pending_approval = {"question": question, "context": context,
                                  "ts": time.time()}
        self._approval_result = None
        deadline = time.time() + 300  # 5 min para decidir
        while time.time() < deadline:
            if self._approval_result is not None:
                result = self._approval_result
                self._pending_approval = None
                self._approval_result = None
                return result
            time.sleep(0.5)
        self._pending_approval = None
        return False  # timeout = negado (falha segura)

    # ------------------------------------------------------------------ #
    def _status(self) -> dict[str, Any]:
        f = self.friday
        engines = f.engines.summary() if hasattr(f, "engines") else {}
        metrics = (f.executor.last_metrics.summary()
                   if hasattr(f.executor, "last_metrics")
                   and f.executor.last_metrics is not None else None)
        return {
            "version": "1.0.0",
            "name": "JIAC FRIDAY",
            "uptime_s": round(time.time() - self.started_at, 1),
            "engines": engines,
            "fast_metrics": metrics,
            "capabilities_count": len(f.registry.all()),
            "agents": [a for a in f.agent_factory.created],
            "workspace": str(f.work_dir),
            "pending_approval": self._pending_approval,
        }

    def _capabilities(self) -> list[dict[str, Any]]:
        out = []
        for cap in self.friday.registry.all():
            try:
                healthy = cap.impl.health()
            except Exception:
                healthy = False
            out.append({
                "name": cap.name,
                "category": cap.category.value,
                "description": cap.description,
                "risk": cap.risk.value,
                "requires_approval": cap.requires_approval,
                "healthy": healthy,
                "tags": cap.tags[:4],
            })
        return out

    def _tasks(self) -> list[dict[str, Any]]:
        out = []
        for t in self.friday.state.list_recent(limit=20):
            steps_done = 0
            steps_total = 0
            if t.plan:
                steps_total = len(t.plan.steps)
                steps_done = sum(1 for s in t.plan.steps
                                 if s.status.value == "completed")
            out.append({
                "id": t.id,
                "objective": t.objective.raw,
                "status": t.status.value,
                "steps_done": steps_done,
                "steps_total": steps_total,
                "updated_at": time.strftime(
                    "%H:%M:%S", time.localtime(t.updated_at)),
            })
        return out

    # ------------------------------------------------------------------ #
    def make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass  # silencia logs HTTP

            def _json(self, data: Any, code: int = 200):
                body = json.dumps(data, ensure_ascii=False, default=str).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _html(self):
                body = _HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            # ---------------------------------------------------------- #
            def do_GET(self):
                path = urlparse(self.path).path
                f = server.friday
                try:
                    if path in ("/", "/index.html"):
                        self._html()
                    elif path == "/api/status":
                        self._json(server._status())
                    elif path == "/api/capabilities":
                        self._json({"capabilities": server._capabilities()})
                    elif path == "/api/tasks":
                        self._json({"tasks": server._tasks()})
                    elif path.startswith("/api/task/"):
                        tid = path.rsplit("/", 1)[-1]
                        self._json(f.status(tid) or {"error": "não encontrada"},
                                   200 if f.status(tid) else 404)
                    elif path == "/api/briefing":
                        city = "Luanda"
                        self._json(f.daily_briefing(city=city))
                    elif path == "/api/alerts":
                        self._json({"alerts": f.alerts(30)})
                    elif path == "/api/agents":
                        self._json({"roles": f.available_agent_roles(),
                                    "created": f.agent_factory.created})
                    elif path == "/api/metrics":
                        m = getattr(f.executor, "last_metrics", None)
                        self._json(m.summary() if m else {"note": "sem missões ainda"})
                    else:
                        self._json({"error": "endpoint desconhecido"}, 404)
                except Exception as e:
                    self._json({"error": f"{type(e).__name__}: {e}"}, 500)

            def do_POST(self):
                path = urlparse(self.path).path
                f = server.friday
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    if path == "/api/objective":
                        objective = str(payload.get("objective", "")).strip()
                        if not objective:
                            self._json({"error": "objective vazio"}, 400)
                            return
                        def _run():
                            try:
                                f.run(objective)
                            except Exception as e:
                                f._log(f"[dashboard] missão falhou: {e}", "warn")
                        threading.Thread(target=_run, daemon=True).start()
                        self._json({"ok": True, "message":
                                    "missão aceite — a executar em background"})
                    elif path == "/api/approve":
                        decision = bool(payload.get("approve", False))
                        server._approval_result = decision
                        self._json({"ok": True, "approved": decision})
                    elif path == "/api/alerts_read":
                        f.proactivity.mark_all_read()
                        self._json({"ok": True})
                    else:
                        self._json({"error": "endpoint desconhecido"}, 404)
                except Exception as e:
                    self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        return Handler

    # ------------------------------------------------------------------ #
    def serve_forever(self):
        self._httpd = ThreadingHTTPServer((self.host, self.port),
                                          self.make_handler())
        print(f"\n╔══════════════════════════════════════════════════╗")
        print(f"║  JIAC FRIDAY — Dashboard v1.0                    ║")
        print(f"║  http://{self.host}:{self.port}                     ║")
        print(f"╚══════════════════════════════════════════════════╝\n")
        self._httpd.serve_forever()

    def start_background(self):
        """Arranca o dashboard num thread (não bloqueia)."""
        self._httpd = ThreadingHTTPServer((self.host, self.port),
                                          self.make_handler())
        t = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        t.start()
        print(f"[dashboard] http://{self.host}:{self.port}")
        return t

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JIAC FRIDAY Dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8500)
    parser.add_argument("--workdir", default="friday_workspace")
    args = parser.parse_args()

    from .orchestrator import Friday
    friday = Friday(work_dir=args.workdir)
    friday.serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
