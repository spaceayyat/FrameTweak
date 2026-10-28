"""Debloat via Remove-AppxPackage (current user) for a curated allow-list only. No wildcards, no scripts."""
import json, os, re, subprocess, sys
from src.core import winproc
from dataclasses import dataclass
from typing import Callable, List, Optional
from src.tweaks.engine import Result

CURATED = {  # name -> (label, category, what removal does)
 "Microsoft.BingNews": ("News", "Microsoft apps", "Removes the News app."),
 "Microsoft.BingWeather": ("Weather", "Microsoft apps", "Removes the Weather app."),
 "Microsoft.GetHelp": ("Get Help", "Microsoft apps", "Removes the Get Help support app."),
 "Microsoft.Getstarted": ("Tips", "Microsoft apps", "Removes the Tips app."),
 "Microsoft.MicrosoftSolitaireCollection": ("Solitaire Collection", "Games", "Removes Solitaire; saved progress in the app is lost."),
 "Microsoft.MicrosoftOfficeHub": ("Microsoft 365 hub", "Microsoft apps", "Removes the Office hub launcher, not installed Office apps."),
 "Microsoft.People": ("People", "Microsoft apps", "Removes the People app."),
 "Microsoft.WindowsFeedbackHub": ("Feedback Hub", "Microsoft apps", "Removes Feedback Hub."),
 "Microsoft.ZuneMusic": ("Media Player (Groove)", "Media", "Removes this media player app."),
 "Microsoft.ZuneVideo": ("Movies & TV", "Media", "Removes Movies & TV."),
 "Microsoft.YourPhone": ("Phone Link", "Microsoft apps", "Removes Phone Link; phone pairing is lost."),
 "Microsoft.MixedReality.Portal": ("Mixed Reality Portal", "Microsoft apps", "Removes Mixed Reality Portal."),
 "Microsoft.Microsoft3DViewer": ("3D Viewer", "Microsoft apps", "Removes 3D Viewer."),
 "Microsoft.SkypeApp": ("Skype (Store app)", "Communication", "Removes the Store version of Skype."),
 "Microsoft.PowerAutomateDesktop": ("Power Automate", "Microsoft apps", "Removes Power Automate; any flows you made in it stop working."),
 "Microsoft.WindowsMaps": ("Maps", "Microsoft apps", "Removes Maps; offline maps are deleted."),
 "Clipchamp.Clipchamp": ("Clipchamp", "Media", "Removes the Clipchamp video editor."),
 "MicrosoftTeams": ("Microsoft Teams (consumer)", "Communication", "Removes the preinstalled consumer Teams chat app, not a work/school Teams install."),
 "Microsoft.OutlookForWindows": ("New Outlook", "Microsoft apps", "Removes the new Outlook app; your mailbox is not deleted."),
 "Microsoft.549981C3F5F10": ("Cortana", "Microsoft apps", "Removes the Cortana app."),
 "Microsoft.BingSearch": ("Bing Search", "Microsoft apps", "Removes the Bing Search app."),
 "Microsoft.Copilot": ("Copilot", "Microsoft apps", "Removes the Copilot app."),
 "Microsoft.Todos": ("Microsoft To Do", "Microsoft apps", "Removes To Do; tasks stay in your Microsoft account."),
}
DENY = re.compile(r"defender|security|store|installer|windows\.|vclibs|native|framework|xbox|gaming|identity|webexperience|xaml|shell|startmenu|runtime|vcl", re.I)
FULLNAME = re.compile(r"^[A-Za-z0-9._~-]+$")

@dataclass
class AppxApp:
    name: str; full_name: str; publisher: str; label: str; category: str; explanation: str; removable: bool
    method: str = "Remove-AppxPackage (current user)"
    size: Optional[int] = None  # Get-AppxPackage doesn't expose size -> shown as Unavailable

def parse_packages(raw: Optional[str]) -> List[dict]:
    if not raw: return []
    try: data = json.loads(raw)
    except json.JSONDecodeError: return []
    data = [data] if isinstance(data, dict) else data
    return [d for d in data if isinstance(d, dict) and d.get("Name") and d.get("PackageFullName")]

def classify(pkgs: List[dict]) -> List[AppxApp]:
    out = []
    for p in pkgs:
        if p.get("IsFramework"): continue
        n = p["Name"]; cur = CURATED.get(n)
        ok = bool(cur) and not DENY.search(n) and not p.get("NonRemovable")
        pub = re.search(r"CN=([^,]+)", p.get("Publisher") or ""); pub = pub.group(1) if pub else "Unavailable"
        label, cat, expl = cur if cur else (n, "Other (not offered for removal)", "Not on FrameTweak's curated list; use Windows Settings → Apps to manage it.")
        out.append(AppxApp(n, p["PackageFullName"], pub, label, cat, expl, ok, "Remove-AppxPackage (current user)" if ok else "Not offered"))
    return sorted(out, key=lambda a: (not a.removable, a.label.lower()))

def scan() -> List[AppxApp]:
    if sys.platform != "win32": return []
    try:
        r = winproc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-AppxPackage | Select-Object Name,PackageFullName,Publisher,IsFramework,NonRemovable | ConvertTo-Json -Compress"],
            timeout=60)
        return classify(parse_packages(r.stdout)) if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError): return []

def _run_remove(full_name: str) -> Optional[str]:
    r = winproc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Remove-AppxPackage -Package $env:FT_PKG -ErrorAction Stop"],
                       timeout=180, env={**os.environ, "FT_PKG": full_name})
    return None if r.returncode == 0 else (r.stderr.strip().splitlines() or ["unknown error"])[0]

def remove(app: AppxApp, scan_fn: Callable = scan, runner: Callable = _run_remove) -> Result:
    if not (app.removable and app.name in CURATED and not DENY.search(app.name) and FULLNAME.fullmatch(app.full_name)):
        return Result(False, "Not eligible for removal. Nothing changed.")
    try: err = runner(app.full_name)
    except Exception as e: err = str(e)
    if err: return Result(False, f"Removal failed: {err}")
    if any(a.full_name == app.full_name for a in scan_fn()): return Result(False, "Command finished but the app is still installed.")
    return Result(True, "Removed and verified. Not auto-reversible; reinstall from the Microsoft Store if needed.")
