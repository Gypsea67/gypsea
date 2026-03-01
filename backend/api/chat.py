"""API: Chat interface — промпты -> Claude Code -> SSE стриминг."""

import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from backend.models import ChatMessage
from backend.core.claude_adapter import get_claude_adapter
from backend.core.config import load_projects
from backend.core.state import add_chat_message, get_chat_history
from backend.core.system_monitor import can_spawn_agent

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/send")
async def send_message(msg: ChatMessage):
    """Отправить промпт агенту. Возвращает agent_id для SSE подписки."""
    projects = load_projects()
    if msg.project not in projects:
        return {"error": f"Project '{msg.project}' not found"}

    if not can_spawn_agent():
        return {"error": "RAM budget exceeded. Kill idle agents first."}

    project = projects[msg.project]

    # Сохранить в историю
    add_chat_message(msg.project, "user", msg.prompt)

    # Запустить Claude Code
    adapter = get_claude_adapter()
    session = await adapter.create_session(
        project=msg.project,
        prompt=msg.prompt,
        work_dir=project.path,
        model=msg.model,
    )

    return {"agent_id": session.agent_id, "project": msg.project}


@router.get("/stream/{agent_id}")
async def stream_agent_output(agent_id: str, request: Request):
    """SSE стриминг вывода агента. Auto-reconnect friendly."""
    adapter = get_claude_adapter()
    session = adapter.get_session(agent_id)

    if not session:
        return {"error": f"Session '{agent_id}' not found"}

    async def event_generator():
        try:
            async for chunk in session.stream_output():
                if await request.is_disconnected():
                    break
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/kill/{agent_id}")
async def kill_agent(agent_id: str):
    """Kill агента. Graceful: SIGTERM -> wait -> SIGKILL. Snapshot diff."""
    adapter = get_claude_adapter()
    result = await adapter.kill_session(agent_id)
    return result


@router.get("/history/{project}")
async def chat_history(project: str, limit: int = 50):
    """История чата по проекту."""
    return get_chat_history(project, limit)
