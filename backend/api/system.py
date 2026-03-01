"""API: системный мониторинг."""

from fastapi import APIRouter
from backend.core.system_monitor import get_system_info, can_spawn_agent
from backend.core.state import get_all_agents, get_all_locks
from backend.core.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
async def system_info():
    """Системная информация: RAM, CPU, Claude processes."""
    info = get_system_info()
    return info.model_dump()


@router.get("/agents")
async def list_agents():
    """Все агенты (все статусы)."""
    return get_all_agents()


@router.get("/locks")
async def list_locks():
    """Все текущие файловые блокировки."""
    return get_all_locks()


@router.get("/can-spawn")
async def check_can_spawn():
    """Можно ли запустить нового агента (RAM бюджет)."""
    settings = get_settings()
    threshold = settings.get("ram_threshold_percent", 80)
    return {
        "can_spawn": can_spawn_agent(threshold),
        "system": get_system_info().model_dump(),
    }


@router.get("/settings")
async def get_current_settings():
    """Текущие настройки."""
    return get_settings()
