"""Safe temp cleanup: allow-listed roots only, never follows symlinks, skips recent/locked files."""
import os, tempfile, time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

PROTECTED_NAMES = {"downloads", "documents", "desktop", "pictures", "videos", "music", "onedrive"}

@dataclass
class Category:
    id: str; name: str; path: str
    default_selected: bool = True  # False for caches whose removal has a visible cost (they rebuild on next use)
    note: str = ""

@dataclass
class CleanResult:
    bytes_removed: int = 0; files_removed: int = 0; skipped: int = 0
    errors: List[str] = field(default_factory=list)

REBUILD = "Rebuilt automatically; the first launch of each game may stutter or load slowly while shaders recompile."

def categories(local_appdata: Optional[str] = None, temp_dir: Optional[str] = None) -> List[Category]:
    """Fixed, allow-listed cleanup locations that exist on this PC. Paths can be injected for tests."""
    local = local_appdata if local_appdata is not None else os.environ.get("LOCALAPPDATA")
    cats = [Category("user_temp", "User temporary files", temp_dir or tempfile.gettempdir())]
    if local:
        j = lambda *p: os.path.join(local, *p)
        cats += [Category("crash_dumps", "Application crash dumps", j("CrashDumps")),
                 Category("wer_reports", "Windows error reports (this user)", j("Microsoft", "Windows", "WER")),
                 Category("dx_shader_cache", "DirectX shader cache (rebuilds on next game launch)", j("D3DSCache"), False, REBUILD),
                 Category("nv_dx_cache", "NVIDIA DirectX shader cache (rebuilds on next game launch)", j("NVIDIA", "DXCache"), False, REBUILD),
                 Category("nv_gl_cache", "NVIDIA OpenGL shader cache (rebuilds on next game launch)", j("NVIDIA", "GLCache"), False, REBUILD),
                 Category("amd_dx_cache", "AMD shader cache (rebuilds on next game launch)", j("AMD", "DxCache"), False, REBUILD)]
    return [c for c in cats if os.path.isdir(c.path)]

def validate_root(path: str, allowed: Iterable[str]) -> str:
    rp = os.path.realpath(path)
    if rp not in {os.path.realpath(a) for a in allowed}: raise ValueError("Path is not an allowed cleanup location")
    if rp == os.path.dirname(rp) or os.path.basename(rp).lower() in PROTECTED_NAMES:
        raise ValueError("Refusing to clean a protected location")
    return rp

def _eligible(root: str, min_age_hours: float):
    cutoff = time.time() - min_age_hours * 3600
    for d, dirs, files in os.walk(root, followlinks=False):
        for f in files:
            p = os.path.join(d, f)
            try:
                if os.path.islink(p): continue
                st = os.stat(p)
                if st.st_mtime < cutoff: yield p, st.st_size
            except OSError: continue

def analyze(path, allowed, min_age_hours=24):
    root = validate_root(path, allowed); n = size = 0
    for _, s in _eligible(root, min_age_hours): n += 1; size += s
    return size, n

def clean(path, allowed, min_age_hours=24) -> CleanResult:
    root = validate_root(path, allowed); r = CleanResult()
    for p, s in list(_eligible(root, min_age_hours)):
        try: os.remove(p); r.bytes_removed += s; r.files_removed += 1
        except OSError as e: r.skipped += 1; r.errors.append(f"{os.path.basename(p)}: {e.strerror or e}")
    for d, _, _ in os.walk(root, topdown=False, followlinks=False):  # prune now-empty dirs, never the root
        if d != root and not os.path.islink(d):
            try: os.rmdir(d)
            except OSError: pass
    return r
