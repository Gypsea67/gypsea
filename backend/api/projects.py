"""API: управление проектами."""

from fastapi import APIRouter
from backend.core.config import load_projects
from backend.core.git_monitor import get_git_monitor
from backend.core.state import get_agents_by_project
from backend.models import ProjectStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/")
async def list_projects() -> list[ProjectStatus]:
    """Список всех проектов с git статусами и активными агентами."""
    projects = load_projects()
    git_monitor = get_git_monitor()

    # Параллельный опрос git status
    paths = {name: p.path for name, p in projects.items()}
    git_statuses = git_monitor.get_all_statuses(list(paths.values()))

    result = []
    for name, project in projects.items():
        agents = get_agents_by_project(name)
        git_status = git_statuses.get(project.path)

        result.append(ProjectStatus(
            name=name,
            path=project.path,
            server=project.server,
            stack=project.stack,
            priority=project.priority.value,
            hot=project.hot,
            git=git_status,
            active_agents=len(agents),
        ))

    return result


@router.get("/{project_name}")
async def get_project(project_name: str):
    """Детальная информация по одному проекту."""
    projects = load_projects()
    if project_name not in projects:
        return {"error": f"Project '{project_name}' not found"}

    project = projects[project_name]
    git_monitor = get_git_monitor()
    git_status = git_monitor.get_status(project.path)
    agents = get_agents_by_project(project_name)

    return {
        "name": project_name,
        "path": project.path,
        "storage": project.storage,
        "server": project.server,
        "stack": project.stack,
        "priority": project.priority.value,
        "hot": project.hot,
        "deploy_config": project.deploy_config.model_dump() if project.deploy_config else None,
        "git": git_status.model_dump(),
        "agents": agents,
    }


@router.post("/{project_name}/git/invalidate")
async def invalidate_git_cache(project_name: str):
    """Сбросить git кеш для проекта (после dep или commit)."""
    projects = load_projects()
    if project_name not in projects:
        return {"error": "Project not found"}

    git_monitor = get_git_monitor()
    git_monitor.invalidate(projects[project_name].path)
    return {"ok": True}
