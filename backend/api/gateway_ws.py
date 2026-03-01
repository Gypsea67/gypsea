"""WebSocket gateway — OpenClaw protocol bridge для ChatClaw.

ChatClaw подключается сюда как к OpenClaw Gateway,
а мы проксируем запросы в Claude Code CLI.
"""

import json
import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.claude_adapter import get_claude_adapter

router = APIRouter()

GATEWAY_TOKEN = "gypsea-local"  # Токен для ChatClaw


@router.websocket("/ws/gateway")
async def gateway_websocket(ws: WebSocket):
    await ws.accept()
    print(f"[Gateway] WebSocket connected from {ws.client}", flush=True)

    # Отправляем challenge
    await ws.send_text(json.dumps({
        "type": "event",
        "event": "connect.challenge",
        "payload": {"nonce": uuid.uuid4().hex, "ts": 0},
    }))

    authenticated = False
    active_tasks: dict[str, asyncio.Task] = {}

    try:
        while True:
            raw = await ws.receive_text()
            frame = json.loads(raw)

            if frame.get("type") != "req":
                continue

            req_id = frame["id"]
            method = frame["method"]
            params = frame.get("params", {})

            # --- connect ---
            if method == "connect":
                token = params.get("auth", {}).get("token", "")
                if token == GATEWAY_TOKEN:
                    authenticated = True
                    print(f"[Gateway] Authenticated successfully", flush=True)
                    await ws.send_text(json.dumps({
                        "type": "res", "id": req_id, "ok": True,
                        "payload": {"protocol": 3, "sessionId": uuid.uuid4().hex},
                    }))
                else:
                    await ws.send_text(json.dumps({
                        "type": "res", "id": req_id, "ok": False,
                        "error": {"code": "auth_failed", "message": "Invalid token"},
                    }))
                continue

            if not authenticated:
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": False,
                    "error": {"code": "not_authenticated", "message": "Connect first"},
                }))
                continue

            # --- agent.identity.get ---
            if method == "agent.identity.get":
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": True,
                    "payload": {"name": "Claude Code", "emoji": "🤖"},
                }))
                continue

            # --- chat.send ---
            if method == "chat.send":
                session_key = params.get("sessionKey", "default")
                message = params.get("message", "")
                run_id = uuid.uuid4().hex

                # ACK immediately
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": True,
                    "payload": {"runId": run_id},
                }))

                # Stream in background
                task = asyncio.create_task(
                    _stream_claude(ws, session_key, message, run_id)
                )
                active_tasks[run_id] = task
                continue

            # --- chat.abort ---
            if method == "chat.abort":
                session_key = params.get("sessionKey", "")
                run_id = params.get("runId", "")
                task = active_tasks.pop(run_id, None)
                if task:
                    task.cancel()
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": True, "payload": {},
                }))
                continue

            # --- chat.history ---
            if method == "chat.history":
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": True,
                    "payload": {"messages": []},
                }))
                continue

            # --- sessions.list ---
            if method == "sessions.list":
                await ws.send_text(json.dumps({
                    "type": "res", "id": req_id, "ok": True,
                    "payload": {"sessions": []},
                }))
                continue

            # --- unknown ---
            await ws.send_text(json.dumps({
                "type": "res", "id": req_id, "ok": False,
                "error": {"code": "unknown_method", "message": f"Unknown: {method}"},
            }))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        for task in active_tasks.values():
            task.cancel()


async def _stream_claude(ws: WebSocket, session_key: str, message: str, run_id: str):
    """Запустить Claude CLI и стримить ответ в формате OpenClaw chat events."""
    adapter = get_claude_adapter()
    accumulated = ""

    try:
        session = await adapter.create_session(
            project="chatclaw",
            prompt=message,
            work_dir="/home/user/gypsea",
            model="sonnet",
        )

        async for chunk in session.stream_output():
            if chunk["type"] == "token":
                accumulated += chunk["data"]
                await ws.send_text(json.dumps({
                    "type": "event",
                    "event": "chat",
                    "payload": {
                        "runId": run_id,
                        "sessionKey": session_key,
                        "state": "delta",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": accumulated}],
                            "timestamp": 0,
                        },
                    },
                }))
            elif chunk["type"] in ("finished", "done"):
                break

        # Final
        await ws.send_text(json.dumps({
            "type": "event",
            "event": "chat",
            "payload": {
                "runId": run_id,
                "sessionKey": session_key,
                "state": "final",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": accumulated}],
                    "timestamp": 0,
                },
            },
        }))

    except asyncio.CancelledError:
        # Aborted
        await ws.send_text(json.dumps({
            "type": "event",
            "event": "chat",
            "payload": {
                "runId": run_id,
                "sessionKey": session_key,
                "state": "aborted",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": accumulated}],
                    "timestamp": 0,
                },
            },
        }))
    except Exception as e:
        try:
            await ws.send_text(json.dumps({
                "type": "event",
                "event": "chat",
                "payload": {
                    "runId": run_id,
                    "sessionKey": session_key,
                    "state": "error",
                    "error": str(e),
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": ""}],
                        "timestamp": 0,
                    },
                },
            }))
        except Exception:
            pass
