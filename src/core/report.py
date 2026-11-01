"""Plain-text system report the user can save and share. Built only from values FrameTweak actually read:
anything unreadable says 'Unavailable', and no FPS or performance numbers are ever invented."""
import os, time
from typing import Iterable, List, Optional, Tuple
from src.core import sysinfo
from src.tweaks import engine

APPLIED = {True: "Applied", False: "Not applied", None: "Unavailable"}
ON_OFF = {True: "On", False: "Off", None: "Unavailable"}

def tweak_status(tweaks: Iterable[engine.Tweak]) -> List[Tuple[str, str]]:
    """(tweak name, 'Applied' | 'Not applied' | 'Unavailable') by reading each setting right now."""
    return [(t.name, APPLIED[engine.is_applied(t)]) for t in tweaks]

def _memory(total: Optional[int], free: Optional[int]) -> str:
    return "Unavailable" if total is None or free is None else f"{sysinfo.fmt_bytes(free)} free of {sysinfo.fmt_bytes(total)}"

def build_report(s: sysinfo.SystemSnapshot, tweaks: List[Tuple[str, str]], actions: List[str], now: Optional[float] = None) -> str:
    u = lambda x: x if x not in (None, "") else "Unavailable"
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now if now is not None else time.time()))
    cores = f" ({s.cpu_cores} threads)" if s.cpu_cores else ""
    lines = ["FrameTweak system report", f"Generated: {when}", "Values FrameTweak could not read are shown as Unavailable. No FPS is measured.", "",
             "System",
             f"  Windows:     {u(s.windows)}" + ("" if s.supported or not s.windows else "  (unsupported version)"),
             f"  CPU:         {u(s.cpu)}{cores}",
             f"  GPU:         {u(s.gpu)}",
             f"  RAM:         {_memory(s.ram_total, s.ram_available)}",
             f"  Disk:        {_memory(s.disk_total, s.disk_free)}",
             f"  Power plan:  {u(s.power_plan)}",
             f"  Game Mode:   {ON_OFF[s.game_mode]}", "", "Tweaks"]
    lines += [f"  {name}: {state}" for name, state in tweaks] or ["  None available"]
    lines += ["", "Recent actions (from the local log)"]
    lines += [f"  {a}" for a in actions] or ["  None recorded yet"]
    if s.notes: lines += ["", "Notes"] + [f"  {n}" for n in s.notes]
    lines += ["", "Review this file before sharing it: it can include app names from your startup and debloat actions."]
    return "\n".join(lines) + "\n"

def save_report(text: str, directory: str) -> str:
    """Write the report as a new file in `directory` (never overwrites) and return its path."""
    os.makedirs(directory, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for n in range(100):
        path = os.path.join(directory, f"FrameTweak-report-{stamp}{'' if n == 0 else f'-{n}'}.txt")
        try:
            with open(path, "x", encoding="utf-8") as f: f.write(text)
            return path
        except FileExistsError: continue
    raise OSError("Could not choose a free report file name")
