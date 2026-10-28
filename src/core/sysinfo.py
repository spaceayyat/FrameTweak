"""Real system detection. Any metric that cannot be read is None (UI shows 'Unavailable')."""
import platform, subprocess, sys
from src.core import winproc
from dataclasses import dataclass, field
from typing import Optional
import psutil

IS_WINDOWS = sys.platform == "win32"

def run_ps(command: str, timeout: int = 8) -> Optional[str]:
    """Run a fixed PowerShell command (never built from user input). Returns stdout or None."""
    if not IS_WINDOWS:
        return None
    try:
        r = winproc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], timeout=timeout)
        out = r.stdout.strip()
        return out if r.returncode == 0 and out else None
    except (OSError, subprocess.SubprocessError):
        return None

def windows_version() -> Optional[str]:
    if not IS_WINDOWS:
        return None
    ver = sys.getwindowsversion()
    name = "Windows 11" if ver.build >= 22000 else "Windows 10" if ver.major == 10 else f"Windows {ver.major}.{ver.minor}"
    return f"{name} (build {ver.build}, {platform.machine()})"

def is_supported_windows() -> bool:
    """Only Windows 10/11 are targeted."""
    return IS_WINDOWS and sys.getwindowsversion().major == 10

def cpu_model() -> Optional[str]:
    return run_ps("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)")

def gpu_names() -> Optional[str]:
    out = run_ps("(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; '")
    return out

def power_plan() -> Optional[str]:
    if not IS_WINDOWS:
        return None
    try:
        r = winproc.run(["powercfg", "/getactivescheme"], timeout=5)
        if r.returncode == 0 and "(" in r.stdout:
            return r.stdout.split("(", 1)[1].rsplit(")", 1)[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return None

def game_mode_enabled() -> Optional[bool]:
    """HKCU\\Software\\Microsoft\\GameBar\\AutoGameModeEnabled; missing value is not assumed."""
    if not IS_WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar") as k:
            return bool(winreg.QueryValueEx(k, "AutoGameModeEnabled")[0])
    except OSError:
        return None

def disk_info(path: Optional[str] = None) -> Optional[tuple]:
    try:
        u = psutil.disk_usage(path or ("C:\\" if IS_WINDOWS else "/"))
        return (u.total, u.free)
    except OSError:
        return None

@dataclass
class SystemSnapshot:
    windows: Optional[str] = None
    supported: bool = False
    cpu: Optional[str] = None
    cpu_cores: Optional[int] = None
    gpu: Optional[str] = None
    ram_total: Optional[int] = None
    ram_available: Optional[int] = None
    disk_total: Optional[int] = None
    disk_free: Optional[int] = None
    power_plan: Optional[str] = None
    game_mode: Optional[bool] = None
    notes: list = field(default_factory=list)

def collect() -> SystemSnapshot:
    s = SystemSnapshot()
    s.windows = windows_version()
    s.supported = is_supported_windows()
    if not IS_WINDOWS:
        s.notes.append("Not running on Windows: Windows-specific metrics are unavailable.")
    s.cpu = cpu_model() or (platform.processor() or None)
    s.cpu_cores = psutil.cpu_count(logical=True)
    s.gpu = gpu_names()
    try:
        m = psutil.virtual_memory(); s.ram_total, s.ram_available = m.total, m.available
    except Exception:
        pass
    d = disk_info()
    if d: s.disk_total, s.disk_free = d
    s.power_plan = power_plan()
    s.game_mode = game_mode_enabled()
    return s

def fmt_bytes(n: Optional[int]) -> str:
    if n is None: return "Unavailable"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
