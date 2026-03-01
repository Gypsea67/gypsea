"""Загрузка конфигурации проектов и настроек."""

import getpass
import json
from pathlib import Path
from typing import Optional
from backend.models import Project, DeployConfig, DeployMethod, ProjectPriority

# Корень проекта Gypsea
GYPSEA_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = GYPSEA_ROOT / "config"
DB_PATH = GYPSEA_ROOT / "gypsea.db"

_projects_cache: Optional[dict[str, Project]] = None
_settings_cache: Optional[dict] = None
_profiles_cache: Optional[dict] = None


def _load_profiles() -> dict:
    """Загрузить profiles.json. Кешируется."""
    global _profiles_cache
    if _profiles_cache is not None:
        return _profiles_cache

    path = CONFIG_DIR / "profiles.json"
    if not path.exists():
        _profiles_cache = {}
        return _profiles_cache

    with open(path) as f:
        _profiles_cache = json.load(f)
    return _profiles_cache


def get_active_profile() -> str:
    """Определить активный профиль. auto → по username."""
    profiles = _load_profiles()
    if not profiles:
        return "work"

    active = profiles.get("active", "auto")
    if active != "auto":
        return active

    # Auto-detect by username
    username = getpass.getuser()
    for profile_name, rule in profiles.get("auto_detect", {}).items():
        if rule.get("username") == username:
            return profile_name

    return "work"


def set_active_profile(name: str) -> None:
    """Переключить активный профиль и сохранить в profiles.json."""
    global _profiles_cache
    profiles = _load_profiles()
    profiles["active"] = name
    _profiles_cache = profiles

    path = CONFIG_DIR / "profiles.json"
    with open(path, "w") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_profiles_info() -> dict:
    """Информация о профилях для API."""
    profiles = _load_profiles()
    return {
        "active": get_active_profile(),
        "configured": profiles.get("active", "auto"),
        "profiles": list(profiles.get("profiles", {}).keys()),
        "overrides": profiles.get("profiles", {}),
    }


def load_projects(force: bool = False) -> dict[str, Project]:
    """Загрузить проекты из config/projects.json. Кешируется."""
    global _projects_cache
    if _projects_cache is not None and not force:
        return _projects_cache

    path = CONFIG_DIR / "projects.json"
    if not path.exists():
        return {}

    with open(path) as f:
        raw = json.load(f)

    # Apply profile overrides
    profile_name = get_active_profile()
    profiles = _load_profiles()
    overrides = profiles.get("profiles", {}).get(profile_name, {})

    projects = {}
    for name, data in raw.items():
        # Merge path override from active profile
        if name in overrides:
            override = overrides[name]
            if override.get("path"):
                data["path"] = override["path"]

        deploy_cfg = None
        if "deploy_config" in data:
            dc = data.pop("deploy_config")
            deploy_cfg = DeployConfig(
                deploy_method=DeployMethod(dc.get("deploy_method", "scp")),
                ssh_command=dc.get("ssh_command", "ssh"),
                owner=dc.get("owner", "www-data"),
                post_deploy=dc.get("post_deploy", []),
                verify=dc.get("verify", []),
                cache_bust=dc.get("cache_bust", {}),
            )

        projects[name] = Project(
            name=name,
            path=data["path"],
            storage=data.get("storage", ""),
            server=data.get("server", ""),
            ssh=data.get("ssh", ""),
            remote_path=data.get("remote_path", ""),
            stack=data.get("stack", ""),
            priority=ProjectPriority(data.get("priority", "medium")),
            hot=data.get("hot", False),
            deploy_config=deploy_cfg,
        )

    _projects_cache = projects
    return projects


def get_settings() -> dict:
    """Загрузить настройки из config/settings.json. Кешируется."""
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    path = CONFIG_DIR / "settings.json"
    if not path.exists():
        return {}

    with open(path) as f:
        _settings_cache = json.load(f)
    return _settings_cache


def invalidate_cache():
    """Сбросить кеш конфигурации (после изменений)."""
    global _projects_cache, _settings_cache, _profiles_cache
    _projects_cache = None
    _settings_cache = None
    _profiles_cache = None
