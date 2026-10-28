"""Startup inspection (Run keys + startup folders) with StartupApproved status."""
import os, sys
from dataclasses import dataclass
from typing import List

BASE = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

@dataclass
class StartupEntry:
    name: str; source: str; command: str; status: str
    hive: str = ""; approved_key: str = ""; value_name: str = ""

def parse_approved(data: bytes) -> str:
    """First byte even = enabled (02/06), odd = disabled (03/07)."""
    if not data: return "Unknown"
    return "Disabled" if data[0] & 1 else "Enabled"

def _approved(winreg, hive, sub):
    d = {}
    try:
        with winreg.OpenKey(hive, BASE + "\\" + sub) as k:
            i = 0
            while True:
                n, v, _ = winreg.EnumValue(k, i); d[n] = parse_approved(bytes(v)); i += 1
    except OSError: pass
    return d

def read_startup_entries() -> List[StartupEntry]:
    if sys.platform != "win32": return []
    import winreg
    out: List[StartupEntry] = []
    run = r"Software\Microsoft\Windows\CurrentVersion\Run"
    for hive, hn in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        ap = _approved(winreg, hive, "Run")
        try:
            with winreg.OpenKey(hive, run) as k:
                i = 0
                while True:
                    n, v, _ = winreg.EnumValue(k, i); i += 1
                    out.append(StartupEntry(n, f"{hn} Run", str(v), ap.get(n, "Enabled"), hn, "Run", n))
        except OSError: pass
    folders = [("HKCU", winreg.HKEY_CURRENT_USER, os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"), "User Startup folder"),
               ("HKLM", winreg.HKEY_LOCAL_MACHINE, os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs\StartUp"), "All-users Startup folder")]
    for hn, hive, folder, label in folders:
        if folder and os.path.isdir(folder):
            ap = _approved(winreg, hive, "StartupFolder")
            for f in sorted(os.listdir(folder)):
                if f.lower() != "desktop.ini":
                    out.append(StartupEntry(os.path.splitext(f)[0], label, os.path.join(folder, f), ap.get(f, "Enabled"), hn, "StartupFolder", f))
    return out
