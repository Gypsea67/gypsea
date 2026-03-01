"""SQLite WAL persistence — состояние агентов, логи, история.

WAL mode: atomic writes, concurrent reads. Урок #5: никогда JSON для mutable shared state.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional
from backend.core.config import DB_PATH


def init_db():
    """Создать таблицы если не существуют. Включить WAL mode."""
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                pid INTEGER,
                started_at TEXT,
                last_heartbeat TEXT,
                last_output TEXT,
                task_description TEXT DEFAULT '',
                model TEXT DEFAULT 'opus'
            );

            CREATE TABLE IF NOT EXISTS file_locks (
                file_path TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_role TEXT DEFAULT '',
                locked_at TEXT NOT NULL,
                task_description TEXT DEFAULT '',
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                agent_id TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS deploy_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                status TEXT NOT NULL,
                output TEXT DEFAULT '',
                files TEXT DEFAULT '[]',
                started_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source TEXT DEFAULT '',
                data TEXT DEFAULT '{}',
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project);
            CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
            CREATE INDEX IF NOT EXISTS idx_chat_project ON chat_history(project);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_deploy_project ON deploy_log(project);
        """)


@contextmanager
def get_connection():
    """Получить SQLite connection с WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# === Agents ===

def upsert_agent(agent_id: str, project: str, status: str = "idle",
                 pid: Optional[int] = None, task: str = "", model: str = "opus"):
    """Создать или обновить агента."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO agents (agent_id, project, status, pid, started_at, last_heartbeat, task_description, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                status=excluded.status, pid=excluded.pid,
                last_heartbeat=excluded.last_heartbeat, task_description=excluded.task_description
        """, (agent_id, project, status, pid, now, now, task, model))


def update_agent_status(agent_id: str, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE agents SET status=?, last_heartbeat=? WHERE agent_id=?",
                      (status, datetime.utcnow().isoformat(), agent_id))


def update_agent_heartbeat(agent_id: str):
    with get_connection() as conn:
        conn.execute("UPDATE agents SET last_heartbeat=? WHERE agent_id=?",
                      (datetime.utcnow().isoformat(), agent_id))


def update_agent_output(agent_id: str):
    with get_connection() as conn:
        conn.execute("UPDATE agents SET last_output=? WHERE agent_id=?",
                      (datetime.utcnow().isoformat(), agent_id))


def get_agent(agent_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        return dict(row) if row else None


def get_all_agents() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY started_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_agents_by_project(project: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agents WHERE project=? AND status IN ('running', 'stale')",
            (project,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_agent(agent_id: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM file_locks WHERE agent_id=?", (agent_id,))
        conn.execute("DELETE FROM agents WHERE agent_id=?", (agent_id,))


# === File Locks ===

def acquire_lock(file_path: str, agent_id: str, role: str = "", task: str = "") -> bool:
    """Попытка захватить файл. True если успешно, False если занят."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT agent_id FROM file_locks WHERE file_path=?", (file_path,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO file_locks (file_path, agent_id, agent_role, locked_at, task_description) VALUES (?,?,?,?,?)",
            (file_path, agent_id, role, datetime.utcnow().isoformat(), task)
        )
        return True


def release_lock(file_path: str, agent_id: str) -> bool:
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM file_locks WHERE file_path=? AND agent_id=?",
            (file_path, agent_id)
        )
        return result.rowcount > 0


def release_all_locks(agent_id: str) -> int:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM file_locks WHERE agent_id=?", (agent_id,))
        return result.rowcount


def get_all_locks() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM file_locks ORDER BY locked_at").fetchall()
        return [dict(r) for r in rows]


# === Cleanup ===

def cleanup_stale_locks(max_age_minutes: int = 30) -> int:
    """Удалить блокировки старше N минут."""
    cutoff = (datetime.utcnow() - timedelta(minutes=max_age_minutes)).isoformat()
    with get_connection() as conn:
        result = conn.execute("DELETE FROM file_locks WHERE locked_at < ?", (cutoff,))
        return result.rowcount


def cleanup_dead_agents() -> int:
    """Пометить агентов без heartbeat > 5 мин как dead."""
    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE agents SET status='dead' WHERE status='running' AND last_heartbeat < ?",
            (cutoff,)
        )
        return result.rowcount


# === Chat History ===

def add_chat_message(project: str, role: str, content: str, agent_id: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_history (project, role, content, agent_id, timestamp) VALUES (?,?,?,?,?)",
            (project, role, content, agent_id, datetime.utcnow().isoformat())
        )


def get_chat_history(project: str, limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_history WHERE project=? ORDER BY timestamp DESC LIMIT ?",
            (project, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# === Events ===

def add_event(event_type: str, source: str = "", data: dict = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO events (event_type, source, data, timestamp) VALUES (?,?,?,?)",
            (event_type, source, json.dumps(data or {}), datetime.utcnow().isoformat())
        )


def get_recent_events(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in reversed(rows):
            d = dict(r)
            d["data"] = json.loads(d["data"])
            result.append(d)
        return result
