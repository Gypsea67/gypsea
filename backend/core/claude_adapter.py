"""Claude Adapter — изоляция взаимодействия с Claude Code CLI.

Весь парсинг, запуск и kill Claude Code — через этот модуль.
Если формат CLI изменится — меняем только этот файл.
Используется --output-format stream-json для real-time стриминга токенов.
"""

import asyncio
import json
import os
import signal
import uuid
from typing import AsyncGenerator, Optional
from datetime import datetime
from backend.core.state import (
    upsert_agent, update_agent_status, update_agent_output,
    release_all_locks, add_event
)


class ClaudeSession:
    """Одна сессия Claude Code CLI."""

    def __init__(self, project: str, prompt: str, work_dir: str,
                 model: str = "opus", agent_id: Optional[str] = None):
        self.project = project
        self.prompt = prompt
        self.work_dir = work_dir
        self.model = model
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.process: Optional[asyncio.subprocess.Process] = None
        self.started_at: Optional[datetime] = None
        self.output_buffer: list[str] = []

    async def start(self) -> str:
        """Запустить Claude Code CLI как subprocess. Возвращает agent_id."""
        cmd = [
            "claude", "--print",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]

        # Model mapping
        model_flags = {
            "opus": "claude-opus-4-6",
            "sonnet": "claude-sonnet-4-6",
            "haiku": "claude-haiku-4-5-20251001",
        }
        if self.model in model_flags:
            cmd.extend(["--model", model_flags[self.model]])

        cmd.append(self.prompt)

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
            env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"} | {"CLAUDE_CODE_HEADLESS": "1"},
        )

        self.started_at = datetime.utcnow()
        upsert_agent(
            self.agent_id, self.project, status="running",
            pid=self.process.pid, task=self.prompt[:200], model=self.model
        )
        add_event("agent_started", self.agent_id, {
            "project": self.project, "prompt": self.prompt[:200]
        })

        return self.agent_id

    async def stream_output(self) -> AsyncGenerator[dict, None]:
        """Стримить вывод Claude Code в реальном времени.

        Формат stream-json: каждая строка stdout — JSON объект.
        content_block_delta содержит текстовые токены.
        """
        if not self.process or not self.process.stdout:
            return

        while True:
            try:
                line = await asyncio.wait_for(
                    self.process.stdout.readline(), timeout=300
                )
            except asyncio.TimeoutError:
                yield {"type": "stale", "data": "No output for 5 minutes"}
                update_agent_status(self.agent_id, "stale")
                break

            if not line:
                break

            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                # Fallback: непарсируемая строка → raw
                yield {"type": "raw", "data": text}
                continue

            event = self._parse_stream_event(obj)
            if event:
                yield event

        # Process ended
        return_code = await self.process.wait()
        final_status = "idle" if return_code == 0 else "killed"
        update_agent_status(self.agent_id, final_status)
        add_event("agent_finished", self.agent_id, {
            "project": self.project, "return_code": return_code
        })

        yield {
            "type": "finished",
            "data": {
                "return_code": return_code,
                "agent_id": self.agent_id,
            }
        }

    def _parse_stream_event(self, obj: dict) -> Optional[dict]:
        """Парсить одно JSON событие из stream-json.

        Ключевые типы:
        - stream_event / content_block_delta → текстовый токен (real-time)
        - assistant → полное сообщение (после stream)
        - result → финальный результат с метриками
        - system → init info (игнорируем)
        """
        obj_type = obj.get("type")

        # Real-time text tokens
        if obj_type == "stream_event":
            event = obj.get("event", {})
            event_type = event.get("type")

            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    token = delta.get("text", "")
                    if token:
                        self.output_buffer.append(token)
                        update_agent_output(self.agent_id)
                        return {"type": "token", "data": token}

            # Tool use events
            if event_type == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    return {"type": "tool_use", "data": {
                        "tool": block.get("name", ""),
                        "id": block.get("id", ""),
                    }}

            return None

        # Final result with cost/usage
        if obj_type == "result":
            cost = obj.get("total_cost_usd", 0)
            duration = obj.get("duration_ms", 0)
            result_text = obj.get("result", "")
            if result_text:
                add_event("agent_result", self.agent_id, {
                    "project": self.project,
                    "cost_usd": cost,
                    "duration_ms": duration,
                })
            return {"type": "result_meta", "data": {
                "cost_usd": cost,
                "duration_ms": duration,
                "num_turns": obj.get("num_turns", 1),
            }}

        # Skip: system init, rate_limit_event, assistant (duplicate of stream)
        return None

    async def kill(self, grace_seconds: int = 10) -> dict:
        """Graceful kill: SIGTERM → wait → SIGKILL. Snapshot diff перед kill."""
        if not self.process:
            return {"error": "No process"}

        snapshot = await self._snapshot_diff()

        # SIGTERM
        try:
            self.process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            pass

        try:
            await asyncio.wait_for(self.process.wait(), timeout=grace_seconds)
        except asyncio.TimeoutError:
            # SIGKILL
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
            await self.process.wait()

        # Cleanup
        locks_released = release_all_locks(self.agent_id)
        update_agent_status(self.agent_id, "killed")
        add_event("agent_killed", self.agent_id, {
            "project": self.project,
            "locks_released": locks_released,
            "had_snapshot": bool(snapshot),
        })

        return {
            "agent_id": self.agent_id,
            "locks_released": locks_released,
            "snapshot": snapshot,
        }

    async def _snapshot_diff(self) -> str:
        """Сохранить git diff перед kill."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff",
                cwd=self.work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return stdout.decode("utf-8", errors="replace")[:10000]
        except Exception:
            return ""

    def get_full_output(self) -> str:
        return "".join(self.output_buffer)


# === Singleton adapter ===

class ClaudeAdapter:
    """Управление всеми Claude Code сессиями."""

    def __init__(self):
        self.sessions: dict[str, ClaudeSession] = {}

    async def create_session(self, project: str, prompt: str, work_dir: str,
                             model: str = "opus") -> ClaudeSession:
        session = ClaudeSession(project, prompt, work_dir, model)
        agent_id = await session.start()
        self.sessions[agent_id] = session
        return session

    async def kill_session(self, agent_id: str, grace_seconds: int = 10) -> dict:
        session = self.sessions.get(agent_id)
        if not session:
            return {"error": f"Session {agent_id} not found"}
        result = await session.kill(grace_seconds)
        del self.sessions[agent_id]
        return result

    def get_session(self, agent_id: str) -> Optional[ClaudeSession]:
        return self.sessions.get(agent_id)

    def get_active_sessions(self) -> list[str]:
        return [aid for aid, s in self.sessions.items() if s.process and s.process.returncode is None]


_adapter: Optional[ClaudeAdapter] = None


def get_claude_adapter() -> ClaudeAdapter:
    global _adapter
    if _adapter is None:
        _adapter = ClaudeAdapter()
    return _adapter
