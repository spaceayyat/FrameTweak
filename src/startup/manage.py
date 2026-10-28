"""Enable/disable startup entries via StartupApproved (what Task Manager uses). Nothing is deleted."""
import sys
from typing import Optional
from src.startup.inspect_startup import BASE, StartupEntry
from src.tweaks.engine import Tweak

ENABLED, DISABLED = "020000000000000000000000", "030000000000000000000000"

def is_admin() -> bool:
    try:
        import ctypes; return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def _hive(n):
    import winreg; return winreg.HKEY_LOCAL_MACHINE if n == "HKLM" else winreg.HKEY_CURRENT_USER

def reg_read(hive: str, key: str, name: str) -> Optional[str]:
    import winreg
    try:
        with winreg.OpenKey(_hive(hive), key) as k: return bytes(winreg.QueryValueEx(k, name)[0]).hex()
    except FileNotFoundError: return None

def reg_write(hive: str, key: str, name: str, val: Optional[str]) -> None:
    import winreg
    if val is None:
        try:
            with winreg.OpenKey(_hive(hive), key, 0, winreg.KEY_SET_VALUE) as k: winreg.DeleteValue(k, name)
        except FileNotFoundError: pass
    else:
        with winreg.CreateKeyEx(_hive(hive), key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, bytes.fromhex(val))

def make_tweak(e: StartupEntry, enable: bool, io=None) -> Tweak:
    rd, wr = io or (reg_read, reg_write); key = f"{BASE}\\{e.approved_key}"
    admin = e.hive == "HKLM"
    sup = (lambda: True) if io else (lambda: sys.platform == "win32" and (not admin or is_admin()))
    return Tweak(f"startup:{e.source}:{e.name}", f"{'Enable' if enable else 'Disable'} startup: {e.name}",
                 f"{'Allows' if enable else 'Stops'} '{e.name}' ({e.source}) from launching at sign-in. The app is not uninstalled and the entry is not deleted.",
                 "Fewer sign-in programs can shorten startup and free background memory.",
                 "The program won't auto-start (e.g. sync or updater tools stay stale). Some apps re-enable themselves.",
                 admin, True, lambda: rd(e.hive, key, e.value_name), lambda v: wr(e.hive, key, e.value_name, v),
                 ENABLED if enable else DISABLED, sup)
