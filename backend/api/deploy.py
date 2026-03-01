"""API: деплой проектов через unified abstraction.

Каждый проект имеет свой deploy_config в projects.json:
- deploy_method: scp | cat_pipe | rsync
- ssh_command: ssh | ssh.exe (WSL ssh зависает для некоторых серверов)
- owner: www-data | shtop | root
- post_deploy: команды после деплоя
- verify: проверки после деплоя
- cache_bust: тип сброса кеша
"""

import asyncio
import subprocess
from datetime import datetime
from fastapi import APIRouter
from backend.models import DeployRequest, DeployMethod
from backend.core.config import load_projects
from backend.core.state import get_connection, add_event
from backend.core.git_monitor import get_git_monitor

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


@router.post("/")
async def deploy_project(req: DeployRequest):
    """Запустить деплой проекта. Unified abstraction по deploy_config."""
    projects = load_projects()
    if req.project not in projects:
        return {"error": f"Project '{req.project}' not found"}

    project = projects[req.project]
    if not project.deploy_config:
        return {"error": f"No deploy_config for '{req.project}'"}

    dc = project.deploy_config
    started_at = datetime.utcnow().isoformat()

    # Log deploy start
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO deploy_log (project, status, started_at) VALUES (?, 'running', ?)",
            (req.project, started_at)
        )
        deploy_id = cursor.lastrowid

    try:
        output_parts = []

        # 1. Deploy files
        if dc.deploy_method == DeployMethod.SCP:
            result = await _deploy_scp(project.path, project.ssh, project.remote_path, dc, req.files)
        elif dc.deploy_method == DeployMethod.CAT_PIPE:
            result = await _deploy_cat_pipe(project.path, project.ssh, project.remote_path, dc, req.files)
        else:
            result = await _deploy_scp(project.path, project.ssh, project.remote_path, dc, req.files)

        output_parts.append(result)

        # 2. Set owner
        if dc.owner:
            owner_result = await _run_remote(
                dc.ssh_command, project.ssh,
                f"chown -R {dc.owner}:{dc.owner} {project.remote_path}"
            )
            output_parts.append(f"Owner: {owner_result}")

        # 3. Post-deploy commands
        for cmd in dc.post_deploy:
            pd_result = await _run_remote(dc.ssh_command, project.ssh, cmd)
            output_parts.append(f"Post-deploy ({cmd}): {pd_result}")

        # 4. Verify
        verify_ok = True
        for check in dc.verify:
            try:
                proc = await asyncio.create_subprocess_shell(
                    check, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                if proc.returncode != 0:
                    verify_ok = False
                    output_parts.append(f"Verify FAILED: {check}")
                else:
                    output_parts.append(f"Verify OK: {check}")
            except Exception as e:
                verify_ok = False
                output_parts.append(f"Verify ERROR: {check} — {e}")

        status = "success" if verify_ok else "warning"
        output = "\n".join(output_parts)

    except Exception as e:
        status = "failed"
        output = str(e)

    # Update deploy log
    finished_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE deploy_log SET status=?, output=?, finished_at=? WHERE id=?",
            (status, output, finished_at, deploy_id)
        )

    # Invalidate git cache
    get_git_monitor().invalidate(project.path)

    add_event("deploy", req.project, {"status": status, "deploy_id": deploy_id})

    return {
        "deploy_id": deploy_id,
        "project": req.project,
        "status": status,
        "output": output,
        "started_at": started_at,
        "finished_at": finished_at,
    }


@router.get("/history/{project}")
async def deploy_history(project: str, limit: int = 10):
    """История деплоев проекта."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM deploy_log WHERE project=? ORDER BY started_at DESC LIMIT ?",
            (project, limit)
        ).fetchall()
        return [dict(r) for r in rows]


async def _deploy_scp(local_path: str, ssh_str: str, remote_path: str,
                      dc, files: list[str]) -> str:
    """Деплой через scp."""
    # Parse SSH string for scp
    parts = ssh_str.split()
    ssh_args = parts[:-1]  # all except user@host
    target = parts[-1]     # user@host

    scp_cmd = [dc.ssh_command.replace("ssh", "scp")]
    # Pass through -i flag if present
    for i, arg in enumerate(ssh_args):
        if arg == "-i" and i + 1 < len(ssh_args):
            scp_cmd.extend(["-i", ssh_args[i + 1]])

    if files:
        results = []
        for f in files:
            local_file = f"{local_path}/{f}"
            remote_file = f"{target}:{remote_path}{f}"
            cmd = scp_cmd + [local_file, remote_file]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            results.append(f"scp {f}: {'OK' if proc.returncode == 0 else stderr.decode()}")
        return "\n".join(results)
    else:
        # Deploy all via scp -r
        cmd = scp_cmd + ["-r", f"{local_path}/.", f"{target}:{remote_path}"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return f"scp -r: {'OK' if proc.returncode == 0 else stderr.decode()}"


async def _deploy_cat_pipe(local_path: str, ssh_str: str, remote_path: str,
                           dc, files: list[str]) -> str:
    """Деплой через cat | ssh (для серверов где WSL ssh зависает)."""
    results = []
    for f in (files or []):
        local_file = f"{local_path}/{f}"
        remote_file = f"{remote_path}{f}"
        # cat file | ssh.exe user@host "cat > remote_path"
        cmd = f'cat "{local_file}" | {dc.ssh_command} {ssh_str.split()[-1]} "cat > {remote_file}"'
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        results.append(f"cat_pipe {f}: {'OK' if proc.returncode == 0 else stderr.decode()}")
    return "\n".join(results) if results else "cat_pipe: no files specified"


async def _run_remote(ssh_command: str, ssh_str: str, command: str) -> str:
    """Выполнить команду на удалённом сервере."""
    parts = ssh_str.split()
    cmd = [ssh_command] + parts[1:] + [command]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode().strip() or stderr.decode().strip() or "OK"
    except Exception as e:
        return f"Error: {e}"
