"""API: FTS5 поиск по lessons и experiences всех проектов."""

import sqlite3
from pathlib import Path
from fastapi import APIRouter
from backend.core.config import load_projects, DB_PATH
from backend.core.state import get_connection

router = APIRouter(prefix="/api/search", tags=["search"])

_fts_initialized = False


def init_fts():
    """Создать FTS5 виртуальную таблицу и индексировать lessons/experiences."""
    global _fts_initialized
    if _fts_initialized:
        return

    with get_connection() as conn:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                project, type, title, content, tags, file_path
            )
        """)

        # Проверяем есть ли данные
        count = conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0]
        if count == 0:
            _index_all_projects(conn)

    _fts_initialized = True


def reindex():
    """Полная переиндексация."""
    global _fts_initialized
    with get_connection() as conn:
        conn.execute("DELETE FROM knowledge_fts")
        _index_all_projects(conn)
    _fts_initialized = True


def _index_all_projects(conn):
    """Загрузить lessons и experiences из всех проектов в FTS5."""
    projects = load_projects()

    for name, project in projects.items():
        storage = Path(project.storage)
        if not storage.exists():
            continue

        # Index lessons-learned.md
        lessons_path = storage / "memory" / "lessons-learned.md"
        if lessons_path.exists():
            content = lessons_path.read_text(encoding="utf-8", errors="replace")
            _index_lessons(conn, name, content, str(lessons_path))

        # Index experiences/*.json
        exp_dir = storage / "memory" / "experiences"
        if exp_dir.exists():
            for f in exp_dir.glob("*.json"):
                if f.name == "index.json":
                    continue
                try:
                    import json
                    data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                    _index_experience(conn, name, data, str(f))
                except Exception:
                    pass


def _index_lessons(conn, project: str, content: str, file_path: str):
    """Разбить lessons-learned.md на отдельные уроки и индексировать."""
    sections = content.split("## #")
    for section in sections[1:]:  # skip header
        lines = section.strip().split("\n")
        if not lines:
            continue
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        # Extract tags
        tags = ""
        for line in lines:
            if "**Теги:**" in line:
                tags = line.split("**Теги:**")[1].strip()

        conn.execute(
            "INSERT INTO knowledge_fts (project, type, title, content, tags, file_path) VALUES (?,?,?,?,?,?)",
            (project, "lesson", title, body, tags, file_path)
        )


def _index_experience(conn, project: str, data: dict, file_path: str):
    """Индексировать один experience JSON."""
    tags = " ".join(data.get("tags", []))
    trajectory = "\n".join(data.get("trajectory", []))
    key_decisions = "\n".join(data.get("key_decisions", []))
    content = f"{trajectory}\n{key_decisions}"

    conn.execute(
        "INSERT INTO knowledge_fts (project, type, title, content, tags, file_path) VALUES (?,?,?,?,?,?)",
        (project, "experience", data.get("id", ""), content, tags, file_path)
    )


@router.get("/")
async def search_knowledge(q: str, project: str = "", limit: int = 20):
    """Полнотекстовый поиск по lessons и experiences."""
    init_fts()

    with get_connection() as conn:
        if project:
            rows = conn.execute(
                "SELECT *, rank FROM knowledge_fts WHERE knowledge_fts MATCH ? AND project=? ORDER BY rank LIMIT ?",
                (q, project, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT *, rank FROM knowledge_fts WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT ?",
                (q, limit)
            ).fetchall()

        return [dict(r) for r in rows]


@router.post("/reindex")
async def trigger_reindex():
    """Принудительная переиндексация."""
    reindex()
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0]
    return {"ok": True, "indexed": count}
