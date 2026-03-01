"""Git мониторинг с кешем и параллельным опросом.

/mnt/d/ (NTFS через WSL2) — медленный I/O, поэтому:
- ThreadPoolExecutor(5) для параллельного опроса
- Кеш 60 сек (invalidation после dep/commit)
- Отдельный поток, не блокирует async event loop
"""

import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from backend.models import GitStatus
from backend.core.config import get_settings


class GitMonitor:
    """Кешированный git status для всех проектов."""

    def __init__(self, max_workers: int = 5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cache: dict[str, tuple[float, GitStatus]] = {}
        settings = get_settings()
        self.cache_ttl = settings.get("git_cache_seconds", 60)

    def get_status(self, project_path: str, force: bool = False) -> GitStatus:
        """Получить git status для одного проекта. Кеш cache_ttl секунд."""
        now = time.time()
        if not force and project_path in self._cache:
            cached_time, cached_status = self._cache[project_path]
            if now - cached_time < self.cache_ttl:
                return cached_status

        status = self._fetch_git_status(project_path)
        self._cache[project_path] = (now, status)
        return status

    def get_all_statuses(self, paths: list[str], force: bool = False) -> dict[str, GitStatus]:
        """Параллельный опрос git status для всех проектов."""
        results = {}
        to_fetch = []

        now = time.time()
        for path in paths:
            if not force and path in self._cache:
                cached_time, cached_status = self._cache[path]
                if now - cached_time < self.cache_ttl:
                    results[path] = cached_status
                    continue
            to_fetch.append(path)

        if to_fetch:
            futures = {
                self.executor.submit(self._fetch_git_status, p): p
                for p in to_fetch
            }
            for future in as_completed(futures, timeout=30):
                path = futures[future]
                try:
                    status = future.result()
                    self._cache[path] = (time.time(), status)
                    results[path] = status
                except Exception as e:
                    results[path] = GitStatus(error=str(e))

        return results

    def invalidate(self, project_path: Optional[str] = None):
        """Сбросить кеш. Если project_path=None — весь кеш."""
        if project_path:
            self._cache.pop(project_path, None)
        else:
            self._cache.clear()

    @staticmethod
    def _fetch_git_status(path: str) -> GitStatus:
        """Получить git status для одного пути. Вызывается из thread pool."""
        if not Path(path).exists():
            return GitStatus(error=f"Path not found: {path}")

        if not (Path(path) / ".git").exists():
            return GitStatus(error="Not a git repository")

        try:
            def _run(cmd: list[str]) -> str:
                r = subprocess.run(
                    cmd, cwd=path, capture_output=True, text=True, timeout=15
                )
                return r.stdout.strip()

            # Branch
            branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])

            # Porcelain status
            porcelain = _run(["git", "status", "--porcelain"])
            modified = 0
            untracked = 0
            staged = 0
            for line in porcelain.split("\n"):
                if not line:
                    continue
                idx, wt = line[0], line[1]
                if idx == "?" and wt == "?":
                    untracked += 1
                elif idx in "MADRC":
                    staged += 1
                elif wt in "MD":
                    modified += 1

            # Ahead/behind
            ahead, behind = 0, 0
            try:
                ab = _run(["git", "rev-list", "--left-right", "--count", f"HEAD...@{{u}}"])
                if ab and "\t" in ab:
                    parts = ab.split("\t")
                    ahead, behind = int(parts[0]), int(parts[1])
            except Exception:
                pass

            # Last commit
            last_commit = _run(["git", "log", "-1", "--format=%s"])
            last_commit_time = _run(["git", "log", "-1", "--format=%ci"])

            return GitStatus(
                branch=branch,
                modified=modified,
                untracked=untracked,
                staged=staged,
                ahead=ahead,
                behind=behind,
                last_commit=last_commit[:100],
                last_commit_time=last_commit_time,
            )

        except subprocess.TimeoutExpired:
            return GitStatus(error="Git timeout (>15s)")
        except Exception as e:
            return GitStatus(error=str(e))


# Singleton
_monitor: Optional[GitMonitor] = None


def get_git_monitor() -> GitMonitor:
    global _monitor
    if _monitor is None:
        _monitor = GitMonitor()
    return _monitor
