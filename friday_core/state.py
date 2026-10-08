"""State Engine — persistência de tarefas em SQLite (retomável)."""

from __future__ import annotations
import json
import sqlite3
import time
from typing import Any, Optional
from .types import Task, TaskStatus, RiskLevel, Objective, Plan, Step


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    objective    TEXT NOT NULL,
    plan         TEXT,
    status       TEXT NOT NULL,
    risk         TEXT NOT NULL,
    current_step TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    completed_at REAL
);
CREATE TABLE IF NOT EXISTS task_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT NOT NULL,
    ts        REAL NOT NULL,
    event     TEXT NOT NULL,
    payload   TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
"""


class StateEngine:
    def __init__(self, db_path: str = "friday_state.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def save(self, task: Task) -> None:
        now = time.time()
        task.updated_at = now
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks "
            "(id, objective, plan, status, risk, current_step, "
            " created_at, updated_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task.id, _serialize_objective(task.objective),
             _serialize_plan(task.plan) if task.plan else None,
             task.status.value, task.risk.value, task.current_step_id,
             task.created_at, task.updated_at, task.completed_at),
        )
        self._conn.commit()

    def load(self, task_id: str) -> Optional[Task]:
        row = self._conn.execute(
            "SELECT id, objective, plan, status, risk, current_step, "
            "       created_at, updated_at, completed_at FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        (tid, obj_json, plan_json, status, risk, current_step,
         created, updated, completed) = row
        objective = _deserialize_objective(obj_json)
        plan = _deserialize_plan(plan_json) if plan_json else None
        return Task(
            id=tid, objective=objective, plan=plan,
            status=TaskStatus(status), risk=RiskLevel(risk),
            current_step_id=current_step,
            created_at=created, updated_at=updated, completed_at=completed,
        )

    def log_event(self, task_id: str, event: str, payload: dict[str, Any] | None = None):
        self._conn.execute(
            "INSERT INTO task_events (task_id, ts, event, payload) VALUES (?, ?, ?, ?)",
            (task_id, time.time(), event, json.dumps(payload or {}, default=str)),
        )
        self._conn.commit()

    def get_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT ts, event, payload FROM task_events WHERE task_id=? ORDER BY ts",
            (task_id,),
        ).fetchall()
        return [{"ts": ts, "event": ev, "payload": json.loads(p)} for ts, ev, p in rows]

    def list_active(self) -> list[Task]:
        rows = self._conn.execute(
            "SELECT id FROM tasks WHERE status IN (?, ?, ?, ?) ORDER BY updated_at DESC",
            (TaskStatus.PENDING.value, TaskStatus.PLANNING.value,
             TaskStatus.EXECUTING.value, TaskStatus.RECOVERING.value),
        ).fetchall()
        return [self.load(r[0]) for r in rows]

    def list_recent(self, limit: int = 20) -> list[Task]:
        rows = self._conn.execute(
            "SELECT id FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,),
        ).fetchall()
        return [self.load(r[0]) for r in rows]

    def close(self):
        self._conn.close()


def _serialize_objective(obj: Objective) -> str:
    return json.dumps({
        "id": obj.id, "raw": obj.raw, "normalized": obj.normalized,
        "intent": obj.intent, "entities": obj.entities,
        "user_id": obj.user_id, "created_at": obj.created_at,
    }, default=str)


def _deserialize_objective(s: str) -> Objective:
    d = json.loads(s)
    return Objective(
        id=d["id"], raw=d["raw"], normalized=d["normalized"],
        intent=d["intent"], entities=d["entities"],
        user_id=d.get("user_id", "default"),
        created_at=d.get("created_at", time.time()),
    )


def _serialize_plan(plan: Plan) -> str:
    return json.dumps({
        "id": plan.id, "objective_id": plan.objective_id,
        "created_at": plan.created_at,
        "steps": [
            {"id": s.id, "description": s.description, "capability": s.capability,
             "inputs": s.inputs, "depends_on": s.depends_on,
             "status": s.status.value, "attempts": s.attempts,
             "max_attempts": s.max_attempts}
            for s in plan.steps
        ],
    }, default=str)


def _deserialize_plan(s: str) -> Plan:
    d = json.loads(s)
    plan = Plan(
        objective_id=d["objective_id"], id=d["id"],
        created_at=d.get("created_at", time.time()), steps=[],
    )
    for sd in d["steps"]:
        plan.steps.append(Step(
            id=sd["id"], description=sd["description"], capability=sd["capability"],
            inputs=sd["inputs"], depends_on=sd.get("depends_on", []),
            status=TaskStatus(sd["status"]),
            attempts=sd.get("attempts", 0), max_attempts=sd.get("max_attempts", 3),
        ))
    return plan
