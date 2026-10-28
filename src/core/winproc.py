"""The ONLY place subprocesses are started. Never shows a console window, never uses a shell."""
import subprocess, sys
CREATE_NO_WINDOW = 0x08000000

def _kw() -> dict:
    if sys.platform != "win32": return {}
    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 0
    return {"creationflags": CREATE_NO_WINDOW, "startupinfo": si}

def run(args, timeout=10, env=None) -> subprocess.CompletedProcess:
    """args must be a list (no shell). stdout/stderr are captured; callers check returncode. Raises on timeout/OSError."""
    if isinstance(args, str) or not all(isinstance(a, str) for a in args): raise TypeError("args must be a list of strings")
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, shell=False, **_kw())
