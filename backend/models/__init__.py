"""Pydantic модели Gypsea Orchestrator."""

from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime


# === Enums ===

class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STALE = "stale"
    DEAD = "dead"
    KILLED = "killed"


class DeployMethod(str, Enum):
    SCP = "scp"
    CAT_PIPE = "cat_pipe"
    RSYNC = "rsync"


class ProjectPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RamZone(str, Enum):
    GREEN = "green"      # < 60%
    YELLOW = "yellow"    # 60-80%
    RED = "red"          # > 80%


# === Config Models ===

class DeployConfig(BaseModel):
    deploy_method: DeployMethod = DeployMethod.SCP
    ssh_command: str = "ssh"
    owner: str = "www-data"
    post_deploy: list[str] = []
    verify: list[str] = []
    cache_bust: dict = {}


class Project(BaseModel):
    name: str
    path: str
    storage: str
    server: str
    ssh: str
    remote_path: str
    stack: str
    priority: ProjectPriority = ProjectPriority.MEDIUM
    hot: bool = False
    deploy_config: Optional[DeployConfig] = None


# === Runtime Models ===

class AgentInfo(BaseModel):
    agent_id: str
    project: str
    status: AgentStatus = AgentStatus.IDLE
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_output: Optional[datetime] = None
    task_description: str = ""
    model: str = "opus"


class SystemInfo(BaseModel):
    ram_total_mb: int = 0
    ram_used_mb: int = 0
    ram_percent: float = 0.0
    ram_zone: RamZone = RamZone.GREEN
    cpu_percent: float = 0.0
    claude_processes: int = 0
    claude_ram_mb: int = 0


class GitStatus(BaseModel):
    branch: str = ""
    modified: int = 0
    untracked: int = 0
    staged: int = 0
    ahead: int = 0
    behind: int = 0
    last_commit: str = ""
    last_commit_time: str = ""
    error: Optional[str] = None


class ProjectStatus(BaseModel):
    name: str
    path: str
    server: str
    stack: str
    priority: str
    hot: bool
    git: Optional[GitStatus] = None
    active_agents: int = 0
    last_deploy: Optional[str] = None


# === API Models ===

class ChatMessage(BaseModel):
    project: str
    prompt: str
    model: str = "opus"


class ChatResponse(BaseModel):
    agent_id: str
    message: str


class DeployRequest(BaseModel):
    project: str
    files: list[str] = []  # empty = deploy all


class DeployStatus(BaseModel):
    project: str
    status: str  # running, success, failed
    output: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class StartupReport(BaseModel):
    stale_locks_cleaned: int = 0
    zombie_processes_killed: int = 0
    orphan_agents_cleaned: int = 0
    paths_verified: int = 0
    paths_missing: list[str] = []
