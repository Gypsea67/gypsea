"""Startup self-check: cleanup orphan locks, zombie processes, stale state."""

import subprocess
import os
from backend.core.config import get_settings, load_projects
from backend.core.state import cleanup_stale_locks, cleanup_dead_agents, get_all_agents, delete_agent
from backend.models import StartupReport


def run_startup_check() -> StartupReport:
    """Запустить все проверки при старте Gypsea. Возвращает отчёт."""
    settings = get_settings()
    report = StartupReport()

    # 1. Cleanup stale file locks (> 30 min by default)
    max_age = settings.get("stale_lock_minutes", 30)
    report.stale_locks_cleaned = cleanup_stale_locks(max_age)

    # 2. Kill zombie Claude processes (in DB but not alive)
    report.zombie_processes_killed = _kill_zombie_processes()

    # 3. Cleanup dead agents
    report.orphan_agents_cleaned = cleanup_dead_agents()

    # 4. Verify project paths exist
    projects = load_projects()
    report.paths_verified = len(projects)
    for name, project in projects.items():
        if not os.path.isdir(project.path):
            report.paths_missing.append(f"{name}: {project.path}")

    return report


def reap_zombie_agents() -> int:
    """Найти агентов в БД с status=running/stale но мёртвым PID. Пометить idle.

    Вызывается при старте и периодически (каждые 30с).
    """
    reaped = 0
    agents = get_all_agents()

    for agent in agents:
        if agent["status"] not in ("running", "stale"):
            continue

        pid = agent.get("pid")
        if not pid:
            continue

        if not _is_process_alive(pid):
            from backend.core.state import update_agent_status, release_all_locks, add_event
            release_all_locks(agent["agent_id"])
            update_agent_status(agent["agent_id"], "idle")
            add_event("zombie_reaped", agent["agent_id"], {
                "project": agent["project"], "pid": pid
            })
            reaped += 1

    return reaped


def _kill_zombie_processes() -> int:
    """Legacy wrapper для startup."""
    return reap_zombie_agents()


def _is_process_alive(pid: int) -> bool:
    """Проверить жив ли процесс через os.kill(pid, 0)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
