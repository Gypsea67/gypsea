"""Мониторинг системных ресурсов: RAM, CPU, процессы Claude."""

import subprocess
import re
from pathlib import Path
from backend.models import SystemInfo, RamZone


def get_system_info() -> SystemInfo:
    """Собрать системную информацию за один проход."""
    ram = _get_ram_info()
    cpu = _get_cpu_percent()
    claude_procs, claude_ram = _get_claude_processes()

    # RAM zones: green < 60%, yellow 60-80%, red > 80%
    zone = RamZone.GREEN
    if ram["percent"] >= 80:
        zone = RamZone.RED
    elif ram["percent"] >= 60:
        zone = RamZone.YELLOW

    return SystemInfo(
        ram_total_mb=ram["total"],
        ram_used_mb=ram["used"],
        ram_percent=ram["percent"],
        ram_zone=zone,
        cpu_percent=cpu,
        claude_processes=claude_procs,
        claude_ram_mb=claude_ram,
    )


def _get_ram_info() -> dict:
    """Читаем /proc/meminfo — быстрее чем psutil."""
    try:
        meminfo = Path("/proc/meminfo").read_text()
        total = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1)) // 1024
        available = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1)) // 1024
        used = total - available
        percent = round((used / total) * 100, 1) if total > 0 else 0
        return {"total": total, "used": used, "percent": percent}
    except Exception:
        return {"total": 0, "used": 0, "percent": 0}


def _get_cpu_percent() -> float:
    """Средняя загрузка CPU (1 мин) из /proc/loadavg."""
    try:
        loadavg = Path("/proc/loadavg").read_text().split()
        load_1m = float(loadavg[0])
        # Нормализуем по количеству ядер
        cpu_count = len([l for l in Path("/proc/cpuinfo").read_text().split("\n") if l.startswith("processor")])
        return round((load_1m / max(cpu_count, 1)) * 100, 1)
    except Exception:
        return 0.0


def _get_claude_processes() -> tuple[int, int]:
    """Найти процессы Claude Code и их суммарный RAM."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        count = 0
        total_ram_kb = 0
        for line in result.stdout.split("\n"):
            if "claude" in line.lower() and "ps aux" not in line:
                count += 1
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        # RSS is column 5 (0-indexed)
                        total_ram_kb += int(parts[5])
                    except (ValueError, IndexError):
                        pass
        return count, total_ram_kb // 1024
    except Exception:
        return 0, 0


def can_spawn_agent(max_ram_percent: float = 80.0) -> bool:
    """Проверить можно ли запустить нового агента по RAM бюджету."""
    info = get_system_info()
    return info.ram_zone != RamZone.RED
