# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Gypsea Orchestrator Clodik Teams — Web GUI for managing projects and Claude Code agents.

| Param | Value |
|-------|-------|
| Stack | FastAPI (Python 3.12) + React 19 + TypeScript 5.9 + Zustand 5 |
| DB | SQLite WAL mode (`gypsea.db`, gitignored) |
| Search | SQLite FTS5 (Phase 1-2), ChromaDB planned (Phase 3) |
| Output streams | SSE (logs, statuses, events) |
| Terminal input | WebSocket (Phase 3) |
| Portable | Tauri (Phase 4) |
| Runtime dir | `~/gypsea/` (ext4, fast I/O) |
| Storage | `/mnt/d/Bloknot/Reels/Work/Projects/gypseaorchestrator/` (symlinked as `storage/`) |

## Build & Run

```bash
# Backend (from ~/gypsea/)
python3 -m uvicorn backend.main:app --port 8765 --reload

# Frontend (from ~/gypsea/frontend/)
npm run dev          # Vite dev server on :5173

# Full stack
./scripts/install.sh  # One-time setup (venv + npm install)
./scripts/run.sh      # Start both backend :8765 and frontend :5173

# Lint frontend
cd frontend && npm run lint

# Build frontend for production
cd frontend && npm run build
```

Note: if `python3 -m venv` fails (missing `python3.12-venv`), install deps with `pip install --user --break-system-packages -r backend/requirements.txt` and run uvicorn without venv. Vite 5.x is pinned for Node 20 compatibility (Vite 7 requires Node 22+).

## Architecture

```
gypsea/
├── backend/                    ← FastAPI (Python)
│   ├── api/
│   │   ├── projects.py         ← GET /api/projects/ — list with git status
│   │   ├── chat.py             ← POST /api/chat/send, GET /api/chat/stream/{id} (SSE)
│   │   ├── deploy.py           ← POST /api/deploy/ — unified deploy abstraction
│   │   ├── system.py           ← GET /api/system/info — RAM gauge, agents, locks
│   │   └── search.py           ← GET /api/search/?q= — FTS5 across all lessons
│   ├── core/
│   │   ├── claude_adapter.py   ← ALL Claude Code CLI interaction isolated here
│   │   ├── state.py            ← SQLite WAL: agents, file_locks, chat_history, events
│   │   ├── config.py           ← Loads config/projects.json + settings.json
│   │   ├── git_monitor.py      ← ThreadPoolExecutor(5), 60s cache, parallel polling
│   │   ├── system_monitor.py   ← /proc/meminfo, RAM zones (green/yellow/red)
│   │   └── startup_check.py    ← Cleanup orphan locks, zombie processes on start
│   ├── models/__init__.py      ← All Pydantic models
│   └── main.py                 ← FastAPI app, CORS, SSE event stream, lifespan
├── frontend/                   ← React + Vite
│   └── src/
│       ├── stores/index.ts     ← Zustand store (projects, system, agents, chat)
│       ├── hooks/useSSE.ts     ← SSE with exponential backoff reconnect + apiFetch helper
│       ├── hooks/useProjects.ts ← Project list fetching with 30s auto-refresh
│       └── components/         ← Dashboard, Chat, SystemMonitor
├── config/
│   ├── projects.json           ← Project registry with deploy_config per project
│   └── settings.json           ← Thresholds (RAM 80%, git cache 60s, etc.)
├── storage -> /mnt/d/.../gypseaorchestrator/  ← Symlink to D: drive
└── gypsea.db                   ← SQLite runtime (gitignored)
```

## Key Architectural Decisions

1. **Claude Adapter pattern** — `claude_adapter.py` isolates ALL interaction with Claude Code CLI. If CLI format changes, only this file needs updating. Graceful fallback: parse failure → raw output.

2. **SSE + WebSocket hybrid** — SSE for output streams (auto-reconnect, firewall-friendly). WebSocket only for terminal input (zero latency). Never use pure WS for one-directional streams.

3. **SQLite WAL, never JSON for mutable state** — Learned from 3 projects (analytics, pmnew, old orchestrator) that JSON without mutex causes race conditions. SQLite WAL gives atomic writes + concurrent reads.

4. **Git polling with cache, not inotify** — `/mnt/d/` is NTFS via WSL2, inotify doesn't work. `ThreadPoolExecutor(5)` with 60s cache. Invalidate cache after deploy/commit.

5. **Startup self-check** — On every start: cleanup stale locks (>30 min), kill zombie processes, verify project paths exist.

6. **Unified Deploy Abstraction** — Each project has `deploy_config` in projects.json: method (scp/cat_pipe/rsync), ssh_command (ssh/ssh.exe for WSL quirks), owner, post_deploy hooks, verify checks, cache_bust type.

## API Patterns

- All API routes prefixed with `/api/`
- SSE streams: `GET /api/events/stream` (global), `GET /api/chat/stream/{agent_id}` (per-agent)
- Agent lifecycle: `POST /api/chat/send` → returns `agent_id` → subscribe to SSE → `POST /api/chat/kill/{agent_id}`
- Git cache invalidation: `POST /api/projects/{name}/git/invalidate`

## Frontend Patterns

- State: Zustand store (`stores/index.ts`), no Redux
- SSE: `useSSE` hook with exponential backoff (`hooks/useSSE.ts`)
- API calls: `apiFetch` helper in `hooks/useSSE.ts`
- Styling: hand-written Tailwind-like utility classes in `index.css` (no Tailwind build step)
- Frontend runs on `:5173`, backend on `:8765` — CORS configured in `main.py`, no Vite proxy

## Storage (D: drive)

Knowledge base lives on D: drive for persistence across WSL resets:
- `storage/memory/lessons-learned.md` — numbered lessons with tags
- `storage/memory/experiences/*.json` — structured trajectories + key decisions
- `storage/pre.md` — project vision document

FTS5 indexes all lessons+experiences from all projects at startup for cross-project search.

## Development Phases

### Phase 1 — MVP Core (current)
- FastAPI backend + SSE + SQLite WAL
- Claude Adapter pattern
- React dashboard with project list + git status
- Chat interface: prompt → Claude Code → SSE streaming
- System monitor: RAM gauge with zones
- Deploy button with unified abstraction
- FTS5 search across lessons

### Phase 2 — Agent System
- File Lock Registry + Claude Code hooks (pre_tool_use/post_tool_use)
- Team visualization (lead → sub-agents tree)
- 3-level health check (PID alive → heartbeat → progress stale)
- Structured output parsing (АНАЛИЗ/ИТОГ → UI cards)
- Snapshot before kill (git diff)
- Circuit breaker (3 crashes → stop)

### Phase 3 — Smart Features
- ChromaDB replacing FTS5 (semantic search)
- xterm.js terminal + @xterm/addon-webgl
- Git worktree isolation (optional)
- CLAUDE.md editor with preview

### Phase 4 — Portable App
- Tauri wrapper
- System tray + auto-start + auto-update
