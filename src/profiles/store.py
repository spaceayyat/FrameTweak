"""Profiles (validated JSON, never executed), measurement history and snapshot comparison."""
import json, os, re, tempfile
from typing import List

KNOWN = {"game_mode": "Enable Windows Game Mode", "power_high": "Use the High performance power plan"}
PRESETS = {
    "Balanced": {"tweaks": ["game_mode"], "notes": "Game Mode only; leaves your power plan alone."},
    "Gaming": {"tweaks": ["game_mode", "power_high"], "notes": "Game Mode and the High performance power plan. Uses more power."},
    "Low Background Activity": {"tweaks": ["game_mode"], "notes": "Game Mode, then use the Startup page and close background apps yourself. FrameTweak never auto-closes processes."},
}
EXE = re.compile(r"^[A-Za-z0-9._ -]{1,64}\.exe$")

def validate_profile(d) -> dict:
    if not isinstance(d, dict): raise ValueError("Profile must be a JSON object")
    name = d.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name): raise ValueError("Invalid profile name")
    tw = d.get("tweaks", [])
    if not isinstance(tw, list) or any(not isinstance(t, str) or t not in KNOWN for t in tw): raise ValueError("Unknown tweak in profile")
    exe = d.get("exe", "") or ""
    if exe and (not isinstance(exe, str) or not EXE.match(exe)): raise ValueError("Game executable must look like game.exe")
    notes = d.get("notes", "") or ""
    if not isinstance(notes, str) or len(notes) > 500: raise ValueError("Notes too long")
    rec = d.get("recommendations", []) or []
    if not isinstance(rec, list) or len(rec) > 10 or any(not isinstance(r, str) or len(r) > 200 for r in rec): raise ValueError("Invalid recommendations")
    return {"name": name.strip(), "exe": exe, "tweaks": list(dict.fromkeys(tw)), "notes": notes, "recommendations": rec}

def _write(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
    os.replace(tmp, path)

def _read(path) -> list:
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8") as f: data = json.load(f)
    if not isinstance(data, list): raise ValueError("Store file malformed")
    return data

class ProfileStore:
    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True); self.pp = os.path.join(directory, "profiles.json"); self.hp = os.path.join(directory, "history.json")
    def presets(self) -> List[dict]:
        return [{"name": n, "exe": "", "recommendations": [], "preset": True, **v} for n, v in PRESETS.items()]
    def custom(self) -> List[dict]:
        return [validate_profile(p) for p in _read(self.pp)]
    def all(self) -> List[dict]:
        return self.presets() + self.custom()
    def save(self, profile: dict) -> dict:
        p = validate_profile(profile)
        if p["name"] in PRESETS: raise ValueError("That name is reserved for a built-in preset")
        _write(self.pp, [x for x in self.custom() if x["name"] != p["name"]] + [p]); return p
    def delete(self, name):
        _write(self.pp, [x for x in self.custom() if x["name"] != name])
    def export(self, name, path):
        p = next((x for x in self.all() if x["name"] == name), None)
        if not p: raise ValueError("No such profile")
        p = {k: v for k, v in p.items() if k != "preset"}
        with open(path, "w", encoding="utf-8") as f: json.dump({"frametweak_profile": 1, **p}, f, indent=2)
    def import_file(self, path) -> dict:
        if os.path.getsize(path) > 100_000: raise ValueError("File too large to be a profile")
        with open(path, encoding="utf-8") as f: d = json.load(f)
        if not isinstance(d, dict) or d.get("frametweak_profile") != 1: raise ValueError("Not a FrameTweak profile file")
        return self.save(d)
    def add_history(self, snap: dict):
        _write(self.hp, (_read(self.hp) + [snap])[-200:])
    def history(self) -> List[dict]:
        return _read(self.hp)
    def delete_history(self, times):
        _write(self.hp, [s for s in _read(self.hp) if s.get("time") not in set(times)])

def compare_snapshots(a: dict, b: dict) -> list:
    fm = lambda x, u: "Unavailable" if x is None else f"{x}{u}"; rows = []
    for k, lab, u in (("cpu_avg", "CPU average", "%"), ("ram_avg", "RAM average", "%"), ("disk_avg", "Disk activity average", " MB/s")):
        x, y = a.get(k), b.get(k); rows.append((lab, fm(x, u), fm(y, u), "n/a" if x is None or y is None else f"{y - x:+.1f}{u}"))
    gm = lambda s: {True: "On", False: "Off", None: "Unavailable"}[s.get("game_mode")]
    rows.append(("Game Mode", gm(a), gm(b), "")); rows.append(("Power plan", a.get("power_plan") or "Unavailable", b.get("power_plan") or "Unavailable", ""))
    return rows
