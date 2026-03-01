"""API: управление профилями и конфигурацией."""

from fastapi import APIRouter
from pydantic import BaseModel
from backend.core.config import (
    get_active_profile,
    set_active_profile,
    get_profiles_info,
    invalidate_cache,
)

router = APIRouter(prefix="/api/config", tags=["config"])


class ProfileSwitch(BaseModel):
    profile: str


@router.get("/profiles")
async def profiles():
    """Список профилей + активный."""
    return get_profiles_info()


@router.post("/profile")
async def switch_profile(body: ProfileSwitch):
    """Переключить активный профиль."""
    info = get_profiles_info()
    if body.profile not in info["profiles"] and body.profile != "auto":
        return {"error": f"Unknown profile: {body.profile}"}

    set_active_profile(body.profile)
    invalidate_cache()
    return {"ok": True, "active": get_active_profile()}
