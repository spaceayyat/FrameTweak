"""Real, individually applied tweaks. Only HKCU/powercfg; nothing needs admin or touches security."""
import re, sys
from src.core import winproc
from src.tweaks.engine import Tweak

WIN = lambda: sys.platform == "win32"
GAMEBAR = r"Software\Microsoft\GameBar"
GUID = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

def _reg_read(path, name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k: return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError: return None

def _reg_write(path, name, val):
    import winreg
    if val is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k: winreg.DeleteValue(k, name)
        except FileNotFoundError: pass
    else:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k: winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(val))

def _powercfg(*args):
    r = winproc.run(["powercfg", *args], timeout=10)
    if r.returncode != 0: raise RuntimeError(r.stderr.strip() or "powercfg failed")
    return r.stdout

def power_read():
    m = GUID.search(_powercfg("/getactivescheme")); 
    if not m: raise RuntimeError("Active power plan not found")
    return m.group(0).lower()

def power_write(guid):
    if not isinstance(guid, str) or not GUID.fullmatch(guid): raise ValueError("Invalid power plan id")
    _powercfg("/setactive", guid)

def high_perf_available():
    try: return HIGH_PERF in _powercfg("/list").lower()
    except Exception: return False

def catalog():
    return [
        Tweak("game_mode", "Enable Windows Game Mode",
              "Sets HKCU\\Software\\Microsoft\\GameBar\\AutoGameModeEnabled to 1.",
              "Game Mode asks Windows to prioritise the foreground game and limit some background activity.",
              "Gains vary and are often small. Undo restores the exact previous state (including 'not set').",
              False, True, lambda: _reg_read(GAMEBAR, "AutoGameModeEnabled"),
              lambda v: _reg_write(GAMEBAR, "AutoGameModeEnabled", v), 1, WIN),
        Tweak("power_high", "Use the High performance power plan",
              "Runs powercfg /setactive for the built-in High performance plan.",
              "Avoids aggressive CPU down-clocking, which can reduce stutter on some desktops.",
              "Higher power use and heat; on laptops it shortens battery life. Plan may not exist on some PCs (then unavailable).",
              False, True, power_read, power_write, HIGH_PERF, lambda: WIN() and high_perf_available()),
    ]
