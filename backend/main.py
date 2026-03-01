"""Gypsea Orchestrator — FastAPI backend.

Точка входа: cd ~/gypsea && python -m uvicorn backend.main:app --port 8765 --reload
"""

import asyncio
import json
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.core.state import init_db, get_recent_events, add_event
from backend.core.startup_check import run_startup_check, reap_zombie_agents
from backend.core.system_monitor import get_system_info
from backend.core.config import get_settings
from backend.api import projects, system, chat, deploy, search, config_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # === STARTUP ===
    init_db()

    # Startup self-check
    report = run_startup_check()
    add_event("startup", "gypsea", {
        "stale_locks": report.stale_locks_cleaned,
        "zombies": report.zombie_processes_killed,
        "orphans": report.orphan_agents_cleaned,
        "paths_missing": report.paths_missing,
    })
    print(f"[Gypsea] Startup check: {report.stale_locks_cleaned} stale locks, "
          f"{report.zombie_processes_killed} zombies, "
          f"{report.orphan_agents_cleaned} orphans cleaned")
    if report.paths_missing:
        print(f"[Gypsea] Missing paths: {report.paths_missing}")

    # Init FTS5 index
    search.init_fts()

    # Periodic zombie reaper (every 30s)
    async def _zombie_reaper():
        while True:
            await asyncio.sleep(30)
            try:
                reaped = reap_zombie_agents()
                if reaped:
                    print(f"[Gypsea] Reaped {reaped} zombie agent(s)", flush=True)
            except Exception as e:
                print(f"[Gypsea] Reaper error: {e}")

    reaper_task = asyncio.create_task(_zombie_reaper())

    yield

    # === SHUTDOWN ===
    reaper_task.cancel()
    print("[Gypsea] Shutting down...")


app = FastAPI(
    title="Gypsea Orchestrator",
    description="Web GUI оркестратор для управления проектами и агентами Claude Code",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "https://geniled.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(projects.router)
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(deploy.router)
app.include_router(search.router)
app.include_router(config_api.router)


# === SSE Event Stream ===

@app.get("/api/events/stream")
async def event_stream():
    """SSE поток событий. Клиент подписывается, получает все events в реальном времени.

    Events: agent_started, agent_finished, agent_killed, deploy, system_update, etc.
    Auto-reconnect через браузерный EventSource.
    """
    async def generate():
        last_id = 0
        settings = get_settings()
        interval = settings.get("refresh_interval_seconds", 5)

        while True:
            events = get_recent_events(limit=10)
            new_events = [e for e in events if e.get("id", 0) > last_id]

            for event in new_events:
                last_id = max(last_id, event.get("id", 0))
                data = json.dumps(event, ensure_ascii=False)
                yield f"id: {last_id}\ndata: {data}\n\n"

            # Periodic system update
            sys_info = get_system_info()
            yield f"event: system\ndata: {json.dumps(sys_info.model_dump())}\n\n"

            await asyncio.sleep(interval)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": time.time(),
    }


# Serve frontend static files in production (must be after all API routes)
_dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="static")
